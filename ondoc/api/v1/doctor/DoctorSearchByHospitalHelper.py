from django.contrib.gis.geos import Point
from django.db.models import F

from ondoc.api.v1.doctor.serializers import DoctorProfileUserViewSerializer
from ondoc.api.v1.procedure.serializers import DoctorClinicProcedureSerializer
from ondoc.doctor import models
from ondoc.api.v1.utils import clinic_convert_timings
from ondoc.api.v1.doctor import serializers
from ondoc.authentication.models import QCModel
from ondoc.doctor.models import Doctor, DoctorClinic
from ondoc.procedure.models import DoctorClinicProcedure, ProcedureCategory, ProcedureToCategoryMapping, \
    get_selected_and_other_procedures, get_included_doctor_clinic_procedure, \
    get_procedure_categories_with_procedures
from datetime import datetime
import re
import json
from django.contrib.staticfiles.templatetags.staticfiles import static

from ondoc.location.models import EntityAddress, EntityUrls
from collections import OrderedDict
from collections import defaultdict


class DoctorSearchByHospitalHelper:
    MAX_DISTANCE = "15000"

    def __init__(self, query_params):
        self.query_params = query_params
        self.count_of_procedure = 0

    def get_filtering_params(self):
        """Helper function that prepare dynamic query for filtering"""
        params = {}
        hospital_type_mapping = {hospital_type[1]: hospital_type[0] for hospital_type in
                                 models.Hospital.HOSPITAL_TYPE_CHOICES}

        filtering_params = []

        specialization_ids = self.query_params.get("specialization_ids", [])
        condition_ids = self.query_params.get("condition_ids", [])

        procedure_ids = self.query_params.get("procedure_ids", [])  # NEW_LOGIC
        procedure_category_ids = self.query_params.get("procedure_category_ids", [])  # NEW_LOGIC
        sits_at_hosp_types = self.query_params.get("sits_at", [])

        if self.query_params.get('hospital_id') is not None:
            filtering_params.append(
                "hospital_id=(%(hospital_id)s)")
            params['hospital_id'] = str(self.query_params.get("hospital_id"))

        if len(condition_ids)>0:
            cs = list(models.MedicalConditionSpecialization.objects.filter(medical_condition_id__in=condition_ids).values_list('specialization_id', flat=True));
            cs = [str(i) for i in cs]
            specialization_ids.extend(cs)

        # " gs.id IN({})".format(",".join(specialization_ids))

        counter=1
        if len(specialization_ids) > 0 and len(procedure_ids)==0 and len(procedure_category_ids)==0:
            sp_str = 'gs.id IN('
            for id in specialization_ids:

                if not counter == 1:
                    sp_str += ','
                sp_str = sp_str + '%('+'specialization'+str(counter)+')s'
                params['specialization'+str(counter)] = id
                counter += 1

            filtering_params.append(
                sp_str+')'
            )

        # if self.query_params.get("sits_at"):
        #     filtering_params.append(
        #         "hospital_type IN(%(sits_at)s)"
        #     )
        #     params['sits_at'] = ", ".join(
        #         [str(hospital_type_mapping.get(sits_at)) for sits_at in self.query_params.get("sits_at")])

        counter = 1
        if self.query_params.get("sits_at"):
            sits_at_str = 'hospital_type IN('
            for hosp_type in sits_at_hosp_types:

                if counter != 1:
                    sits_at_str += ', '
                sits_at_str = sits_at_str + '%(' + 'sits_at' + str(counter) + ')s'
                params['sits_at' + str(counter)] = hospital_type_mapping.get(hosp_type)
                counter += 1

            filtering_params.append(
                sits_at_str + ')'
            )

        if procedure_category_ids and not procedure_ids:  # NEW_LOGIC
            preferred_procedure_ids = list(
                ProcedureCategory.objects.select_related('preferred_procedure').filter(pk__in=procedure_category_ids, is_live=True, preferred_procedure__is_enabled=True).values_list(
                    'preferred_procedure_id', flat=True))
            procedure_ids = preferred_procedure_ids

        # if len(procedure_ids) > 0:  # NEW_LOGIC
        #     ps = list(procedure_ids)
        #     ps = [str(i) for i in ps]
        #     procedure_mapped_ids.extend(ps)
        #     filtering_params.append(
        #         " dcp.procedure_id IN({})".format(",".join((procedure_ids))))
        counter = 1
        if len(procedure_ids) > 0:
            dcp_str = 'dcp.procedure_id IN('
            for id in procedure_ids:
                if not counter == 1:
                    dcp_str += ','
                dcp_str = dcp_str + '%(' + 'procedure' + str(counter) + ')s'
                params['procedure' + str(counter)] = id
                counter += 1
            filtering_params.append(
                dcp_str + ')'
            )

        if len(procedure_ids) == 0 and self.query_params.get("min_fees") is not None:
            filtering_params.append(
                # "deal_price>={}".format(str(self.query_params.get("min_fees")))
                "deal_price>=(%(min_fees)s)")
            params['min_fees'] = str(self.query_params.get("min_fees"))
        if len(procedure_ids) == 0 and self.query_params.get("max_fees") is not None:
            filtering_params.append(
                # "deal_price<={}".format(str(self.query_params.get("max_fees"))))
                "deal_price<=(%(max_fees)s)")
            params['max_fees'] = str(self.query_params.get("max_fees"))
        if self.query_params.get("is_female"):
            filtering_params.append(
                "gender='f'"
            )

        if self.query_params.get("is_available"):
            current_time = datetime.now()
            current_hour = round(float(current_time.hour) + (float(current_time.minute)*1/60), 2) + .75
            filtering_params.append(
                'dct.day=(%(current_time)s) and dct.end>=(%(current_hour)s)')
            params['current_time'] = str(current_time.weekday())
            params['current_hour'] = str(current_hour)

        if self.query_params.get("doctor_name"):
            name = self.query_params.get("doctor_name").lower().strip()
            removals = ['doctor.','doctor ','dr.','dr ']
            for rm in removals:
                # if name.startswith(rm):
                if name.startswith(rm):
                    name = name[len(rm):].strip()
                    break

                # stripped = name.lstrip(rm)
                # if len(stripped) != len(name):
                #     name = stripped
                #     break
            search_key = re.findall(r'[a-z0-9A-Z.]+', name)
            # search_key = re.findall(r'[a-z0-9A-Z.]+', self.query_params.get("doctor_name"))
            search_key = " ".join(search_key).lower()

            search_key = "".join(search_key.split("."))
            filtering_params.append(
                "d.search_key ilike (%(doctor_name)s)"
                    )
            params['doctor_name'] = '%'+search_key+'%'
        if self.query_params.get("hospital_name"):
            search_key = re.findall(r'[a-z0-9A-Z.]+', self.query_params.get("hospital_name"))
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            filtering_params.append(
                "h.search_key ilike (%(hospital_name)s)")
            params['hospital_name'] = '%' + search_key + '%'

        result = {}
        if not filtering_params:
            result['string'] = "1=1"
            result['params'] = params
            return result

        result['string'] = " and ".join(filtering_params)
        result['params'] = params
        if len(procedure_ids) > 0:
            result['count_of_procedure'] = len(procedure_ids)
            self.count_of_procedure = len(procedure_ids)
        return result

    def get_ordering_params(self):

        if self.query_params.get('url') and (not self.query_params.get('sort_on') \
                                             or self.query_params.get('sort_on')=='distance'):
            return ' distance, priority desc ', ' rnk=1 '

        bucket_size=2000

        if self.count_of_procedure:
            order_by_field = ' distance, total_price '
            rank_by = "rnk=1"
            if self.query_params.get('sort_on'):
                if self.query_params.get('sort_on') == 'experience':
                    order_by_field = ' practicing_since ASC, distance ASC '
                    rank_by = "rnk=1"
                elif self.query_params.get('sort_on') == 'fees':
                    order_by_field = " total_price ASC, distance ASC "
                    rank_by = "rnk=1"
                elif self.query_params.get('sort_on') == 'distance':
                    order_by_field = " distance ASC, total_price ASC "
                    rank_by = "rnk=1"
            else:
                order_by_field = " floor(distance/{bucket_size}) ASC, distance, total_price ASC".format(bucket_size=str(bucket_size))
                rank_by = "rnk=1"
            order_by_field = "{}, {} ".format(' enabled_for_online_booking DESC ' ,order_by_field)
        else:
            if self.query_params.get('sort_on'):
                if self.query_params.get('sort_on') == 'experience':
                    order_by_field = ' practicing_since ASC, distance ASC, priority desc '
                    rank_by = " rnk=1 "
                elif self.query_params.get('sort_on') == 'fees':
                    order_by_field = " deal_price ASC, distance ASC, priority desc "
                    rank_by = " rnk=1 "
                elif self.query_params.get('sort_on') == 'distance':
                    order_by_field = " distance ASC, deal_price ASC, priority desc "
                    rank_by = " rnk=1 "
            else:
                order_by_field = ' floor(distance/{bucket_size}) ASC, is_license_verified DESC, distance, priority desc '.format(bucket_size=str(bucket_size))
                rank_by = "rnk=1"

            order_by_field = "{}, {} ".format(' enabled_for_online_booking DESC ', order_by_field)

        return order_by_field, rank_by

    def prepare_raw_query(self, filtering_params, order_by_field, rank_by, page):

        if page<1:
            page =1

        page_start = (page-1)*20
        page_end = page*20

        longitude = str(self.query_params["longitude"])
        latitude = str(self.query_params["latitude"])
        max_distance = str(
            self.query_params.get('max_distance') * 1000 if self.query_params.get(
                'max_distance') and self.query_params.get(
                'max_distance') * 1000 < int(DoctorSearchByHospitalHelper.MAX_DISTANCE) else DoctorSearchByHospitalHelper.MAX_DISTANCE)
        min_distance = self.query_params.get('min_distance')*1000 if self.query_params.get('min_distance') else 0
        # max_distance = 10000000000000000000000
        data = dict()

        specialization_ids = self.query_params.get("specialization_ids", [])
        condition_ids = self.query_params.get("condition_ids", [])

        if self.count_of_procedure:
            rank_part = "Row_number() OVER( PARTITION BY doctor_id, hospital_id ORDER BY " \
                           "distance, total_price ASC) rnk "
            if self.query_params.get('sort_on') == 'fees':
                rank_part = " Row_number() OVER( partition BY doctor_id, hospital_id " \
                            "ORDER BY total_price ASC, distance) rnk " \

            query_string = "SELECT *, " \
                           "ROW_NUMBER () OVER (ORDER BY {order_by_field}) order_rank " \
                           "FROM (SELECT " \
                           " *, {rank_part} " \
                           "FROM (SELECT city, building, locality, hospital_name, name, deal_price, mrp, distance, procedure_deal_price," \
                           "is_live, is_license_verified, " \
                           "doctor_id, practicing_since, doctor_clinic_id, doctor_clinic_timing_id, procedure_id," \
                           "enabled_for_online_booking, is_license_verified, priority, " \
                           "doctor_clinic_deal_price, hospital_id , count_per_clinic, sum_per_clinic, sum_per_clinic+doctor_clinic_deal_price as total_price FROM " \
                           "(SELECT " \
                           "COUNT(procedure_id) OVER (PARTITION BY dct.id) AS count_per_clinic, " \
                           "SUM(dcp.deal_price) OVER (PARTITION BY dct.id) AS sum_per_clinic, " \
                           "St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location) AS distance, " \
                           "dcp.deal_price AS procedure_deal_price, " \
                           "dct.deal_price, dct.mrp, d.is_live, " \
                           "h.locality, h.city,h.building, h.name hospital_name, d.name, " \
                           "d.id AS doctor_id, practicing_since, " \
                           "d.enabled_for_online_booking and dc.enabled_for_online_booking and h.enabled_for_online_booking as enabled_for_online_booking, d.is_license_verified, dc.priority, " \
                           "dc.id AS doctor_clinic_id,  dct.id AS doctor_clinic_timing_id, dcp.id AS doctor_clinic_procedure_id, " \
                           "dcp.procedure_id, dct.deal_price AS doctor_clinic_deal_price, " \
                           "dc.hospital_id AS hospital_id FROM doctor d " \
                           "INNER JOIN doctor_clinic dc ON d.id = dc.doctor_id " \
                           "and dc.enabled=true and d.is_live = true and d.is_test_doctor is False and d.is_internal is False " \
                           "INNER JOIN hospital h ON h.id = dc.hospital_id AND h.is_live=true " \
                           "INNER JOIN doctor_clinic_timing dct ON dc.id = dct.doctor_clinic_id " \
                           "INNER JOIN doctor_clinic_procedure dcp ON dc.id = dcp.doctor_clinic_id " \
                           "WHERE {filtering_params} AND " \
                           "St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location, (%(max_distance)s)) AND " \
                           "St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location, (%(min_distance)s)) = false " \
                           " ) " \
                           "AS tempTable WHERE count_per_clinic={count_of_procedure}) AS tempTable2) " \
                           "x WHERE {rank_by} ".format(
                rank_part = rank_part, filtering_params=filtering_params.get('string'),
                count_of_procedure=filtering_params.get('count_of_procedure'),
                rank_by=rank_by, order_by_field=order_by_field)


            query = ''' select * from (
                    select *, max(hosp_rank) over(partition by 1) result_count from (
                    select *, dense_rank() over(order by rank) as hosp_rank from ( 
                    select  *, 
                    ROW_NUMBER() OVER (PARTITION BY hospital_id order by order_rank) AS row_num,
                    min (order_rank) OVER (PARTITION BY hospital_id) rank 
                     from ({query_string})y )z where row_num<=10
                    )g
                    )a 
                    where hosp_rank<=(%(page_end)s) and hosp_rank>(%(page_start)s) order by hosp_rank, row_num
                    '''.format(query_string=query_string)


        else:
            sp_cond = ''
            min_dist_cond = ''
            rank_part = " Row_number() OVER( partition BY d.id, h.id  ORDER BY " \
                "St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location),dct.deal_price ASC) rnk " \


            if len(specialization_ids)>0 or len(condition_ids)>0:
                sp_cond = " LEFT JOIN doctor_practice_specialization ds on ds.doctor_id = d.id " \
                       " LEFT JOIN practice_specialization gs on ds.specialization_id = gs.id "
            if min_distance>0:
                min_dist_cond = " and St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location, (%(min_distance)s)) = false "

            if self.query_params.get('sort_on') == 'fees':
                rank_part = " Row_number() OVER( partition BY d.id, h.id  ORDER BY " \
                            "dct.deal_price, St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location) ASC) rnk " \

            query_string = "SELECT * ," \
                           " ROW_NUMBER () OVER (ORDER BY {order_by_field}) order_rank " \
                           "FROM (select d.name, h.building, h.name hospital_name, d.is_license_verified, dct.mrp, dct.deal_price, " \
                           " h.sublocality, h.locality, h.city, " \
                           "{rank_part}, " \
                           "St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location) distance, " \
                           "d.id as doctor_id, " \
                           "dc.id as doctor_clinic_id,  " \
                           "dct.id as doctor_clinic_timing_id,practicing_since, " \
                           "d.enabled_for_online_booking and dc.enabled_for_online_booking and h.enabled_for_online_booking as enabled_for_online_booking, " \
                           "priority, d.is_live, " \
                           "dc.hospital_id as hospital_id FROM doctor d " \
                           "INNER JOIN doctor_clinic dc ON d.id = dc.doctor_id and dc.enabled=true and d.is_live=true " \
                           "and d.is_test_doctor is False and d.is_internal is False " \
                           "INNER JOIN hospital h ON h.id = dc.hospital_id and h.is_live=true " \
                           "INNER JOIN doctor_clinic_timing dct ON dc.id = dct.doctor_clinic_id " \
                           "{sp_cond}" \
                           "WHERE {filtering_params}" \
                           " and St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location, (%(max_distance)s)) " \
                           "{min_dist_cond}" \
                           " )x " \
                           "where {rank_by}".format(rank_part=rank_part, sp_cond=sp_cond, \
                                                                              filtering_params=filtering_params.get(
                                                                                  'string'), \
                                                                              min_dist_cond=min_dist_cond,
                                                                              order_by_field=order_by_field, \
                                                                              rank_by=rank_by)

            query = ''' select * from (
                    select *, max(hosp_rank) over(partition by 1) result_count from (
                    select *, dense_rank() over(order by rank) as hosp_rank from ( 
                    select  *, 
                    ROW_NUMBER() OVER (PARTITION BY hospital_id order by order_rank) AS row_num,
                    min (order_rank) OVER (PARTITION BY hospital_id) rank 
                     from ({query_string})y )z where row_num<=10
                    )g
                    )a 
                    where hosp_rank<=(%(page_end)s) and hosp_rank>(%(page_start)s) order by hosp_rank, row_num
                    '''.format(query_string=query_string)



        if not filtering_params.get('params'):
            filtering_params['params'] = dict()

        # if filtering_params.get('params'):
        #     filtering_params.get('params')['longitude'] = longitude
        #     filtering_params.get('params')['latitude'] = latitude
        #     filtering_params.get('params')['min_distance'] = min_distance
        #     filtering_params.get('params')['max_distance'] = max_distance
        # else:
        filtering_params['params']['longitude'] = longitude
        filtering_params['params']['latitude'] = latitude
        filtering_params['params']['min_distance'] = min_distance
        filtering_params['params']['max_distance'] = max_distance
        filtering_params['params']['page_start'] = (page-1)*20
        filtering_params['params']['page_end'] = page*20


        return {'params':filtering_params.get('params'), 'query': query}

    def count_hospitals(self, doctor):
        return len([h for h in doctor.hospitals.all() if h.is_live == True])

    def get_distance(self, doctor, doctor_clinic_mapping):
        current_location = Point(self.query_params.get("longitude"), self.query_params.get("latitude"),
                                srid=4326)
        for hospital in doctor.hospitals.all():
            if hospital.id == doctor_clinic_mapping[doctor.id]:
                return current_location.distance(hospital.location)*100
        return ""

    def get_doctor_fees(self, doctor_clinic, doctor_availability_mapping):
        if not doctor_clinic:
            return
        for doctor_clinic_timing in doctor_clinic.availability.all():
            if doctor_clinic_timing.id == doctor_availability_mapping[doctor_clinic.doctor.id]:
                return doctor_clinic_timing.deal_price, doctor_clinic_timing.mrp
                # return doctor_hospital.deal_price
        return None

    def get_hos_address(self,result):
        address = []

        if result.get('building'):
            address.append(self.ad_str(result.get('building')))
        if result.get('sublocality'):
            address.append(self.ad_str(result.get('sublocality')))
        if result.get('locality'):
            address.append(self.ad_str(result.get('locality')))
        if result.get('city'):
            address.append(self.ad_str(result.get('city')))
        # if self.state:
        #     address.append(self.ad_str(self.state))
        # if self.country:
        #     address.append(self.ad_str(self.country))
        result = []
        ad_uinq = set()
        for ad in address:
            ad_lc = ad.lower()
            if ad_lc not in ad_uinq:
                ad_uinq.add(ad_lc)
                result.append(ad)

        return ", ".join(result)

    def ad_str(self, string):
        return str(string).strip().replace(',', '')

    def prepare_search_response(self, doctor_search_result, doctor_ids, request):
        entity_ids = doctor_ids

        id_url_dict = dict()
        entities = EntityUrls.objects.filter(entity_id__in=entity_ids, is_valid='t',
                                           sitemap_identifier='DOCTOR_PAGE').values('entity_id', 'url')

        # for entity in entities:
        #     id_url_dict[entity['id']]=entity['url']

        # print(entity)
        for data in entities:
            id_url_dict[data['entity_id']] = data['url']


        #doctor_clinic_mapping = {data.get("doctor_id"): data.get("hospital_id") for data in doctor_clinics}
        # doctor_availability_mapping = {data.get("doctor_id"): data.get("doctor_clinic_timing_id") for data in
        #                                doctor_search_result}
        category_ids = self.query_params.get("procedure_category_ids", [])
        procedure_ids = self.query_params.get("procedure_ids", [])
        category_ids = [int(x) for x in category_ids]
        procedure_ids = [int(x) for x in procedure_ids]

        if len(category_ids)>0 or len(procedure_ids)>0:
            doctor_clinic_ids = [data.get("doctor_clinic_id") for data in doctor_search_result]
            doctor_clinics = DoctorClinic.objects.filter(id__in=doctor_clinic_ids).prefetch_related('hospital','procedures_from_doctor_clinic__procedure__parent_categories_mapping')
            doctor_clinic_mapping = dict()
            for dc in doctor_clinics:
                doctor_clinic_mapping[dc.id] = dc


        selected_procedure_ids, other_procedure_ids = get_selected_and_other_procedures(category_ids, procedure_ids)

        hospital_card = OrderedDict()

        from ondoc.coupon.models import Coupon
        search_coupon = Coupon.get_search_coupon(request.user)

        for result in doctor_search_result:
            
            existing = hospital_card.get(result['hospital_id'])
            if not existing:
                h_data = {}
                h_data['address'] = self.get_hos_address(result)
                # h_data['address'] = ", ".join([result["locality"], result["city"]])
                h_data['hospital_id'] = result["hospital_id"]
                h_data['doctors'] = []
                h_data['hospital_name'] = result["hospital_name"]
                h_data['procedure_categories'] = []
                hospital_card[h_data['hospital_id']] = h_data

                if len(category_ids)>0 or len(procedure_ids)>0:

                    all_doctor_clinic_procedures = list(doctor_clinic_mapping[result["doctor_clinic_id"]].procedures_from_doctor_clinic.all())
                    selected_procedures_data = get_included_doctor_clinic_procedure(all_doctor_clinic_procedures,
                                                                                    selected_procedure_ids)
                    other_procedures_data = get_included_doctor_clinic_procedure(all_doctor_clinic_procedures,
                                                                                 other_procedure_ids)
                    selected_procedures_serializer = DoctorClinicProcedureSerializer(selected_procedures_data,
                                                                                     context={'is_selected': True,
                                                                                              'category_ids': category_ids},
                                                                                     many=True)
                    other_procedures_serializer = DoctorClinicProcedureSerializer(other_procedures_data,
                                                                                  context={'is_selected': False,
                                                                                           'category_ids': category_ids},
                                                                                  many=True)
                    selected_procedures_list = list(selected_procedures_serializer.data)
                    other_procedures_list = list(other_procedures_serializer.data)
                    final_result = get_procedure_categories_with_procedures(selected_procedures_list,
                                                                                other_procedures_list)

                    h_data['procedure_categories'] = final_result
                existing = h_data

            discounted_price = result["deal_price"] if not search_coupon else search_coupon.get_search_coupon_discounted_price(result["deal_price"])

            d_data = {}    
            d_data["id"] = result["doctor_id"]
            d_data["doctor_id"] = result["doctor_id"]
            d_data["deal_price"] = result["deal_price"]
            d_data["discounted_fees"] = result["deal_price"]
            d_data["discounted_price"] = discounted_price
            d_data["is_license_verified"] = result["is_license_verified"]
            d_data["distance"] = result["distance"]/1000
            d_data["mrp"] = result["mrp"]
            d_data["is_live"] = result["is_live"]
            d_data["enabled_for_online_booking"] = result["enabled_for_online_booking"]
            d_data["is_gold"] = False
            d_data["name"] = result["name"]
            d_data["display_name"] = "Dr. "+result["name"]
            d_data["url"] = id_url_dict.get(result["doctor_id"],"")



            existing["doctors"].append(d_data)

        return hospital_card.values()



        for doctor in doctor_data:

            doctor_clinics = [doctor_clinic for doctor_clinic in doctor.doctor_clinics.all() if
                              doctor_clinic.hospital_id == doctor_clinic_mapping[doctor_clinic.doctor_id]]
            doctor_clinic = doctor_clinics[0]
            filtered_deal_price, filtered_mrp = self.get_doctor_fees(doctor_clinic, doctor_availability_mapping)
            # filtered_fees = self.get_doctor_fees(doctor, doctor_availability_mapping)
            min_deal_price = None
            min_price = dict()
            for data in doctor_clinic.availability.all():
                if min_deal_price is None or min_deal_price > data.deal_price:
                    min_deal_price = data.deal_price
                    min_price = {
                        "deal_price": data.deal_price,
                        "mrp": data.mrp
                    }
            # min_fees = min([data.get("deal_price") for data in serializer.data if data.get("deal_price")])
            if not doctor_clinic:
                hospitals = []
            else:
                all_doctor_clinic_procedures = list(doctor_clinic.procedures_from_doctor_clinic.all())
                selected_procedures_data = get_included_doctor_clinic_procedure(all_doctor_clinic_procedures,
                                                                                selected_procedure_ids)
                other_procedures_data = get_included_doctor_clinic_procedure(all_doctor_clinic_procedures,
                                                                             other_procedure_ids)
                selected_procedures_serializer = DoctorClinicProcedureSerializer(selected_procedures_data,
                                                                                 context={'is_selected': True,
                                                                                          'category_ids': category_ids},
                                                                                 many=True)
                other_procedures_serializer = DoctorClinicProcedureSerializer(other_procedures_data,
                                                                              context={'is_selected': False,
                                                                                       'category_ids': category_ids},
                                                                              many=True)
                selected_procedures_list = list(selected_procedures_serializer.data)
                other_procedures_list = list(other_procedures_serializer.data)
                final_result = get_procedure_categories_with_procedures(selected_procedures_list,
                                                                        other_procedures_list)
                # fees = self.get_doctor_fees(doctor, doctor_availability_mapping)

                # enable_online_booking = False
                # if doctor_clinic and doctor and doctor_clinic.hospital:
                #     if doctor.enabled_for_online_booking and doctor_clinic.hospital.enabled_for_online_booking and doctor_clinic.enabled_for_online_booking:
                #         enable_online_booking = True

                hospitals = [{
                    # "enabled_for_online_booking": enable_online_booking,
                    "hospital_name": doctor_clinic.hospital.name,
                    "address": ", ".join(
                        [value for value in [doctor_clinic.hospital.sublocality, doctor_clinic.hospital.locality] if
                         value]),
                    "short_address": doctor_clinic.hospital.get_short_address(),
                    "hospital_id": doctor_clinic.hospital.id,
                    # "discounted_fees": min_price["deal_price"],
                    "procedure_categories": final_result
                }]

            thumbnail = doctor.get_thumbnail()
            url = None

            if doctor.pk in id_url_dict.keys():
                url = id_url_dict[doctor.pk]

            opening_hours = None
            if doctor_clinic.availability.exists():
                opening_hours = '%.2f-%.2f' % (doctor_clinic.availability.all()[0].start,
                                                   doctor_clinic.availability.all()[0].end),

            temp = {
                "doctor_id": doctor.id,
                "enabled_for_online_booking": doctor.enabled_for_online_booking,
                "is_license_verified" : doctor.is_license_verified,
                "hospital_count": self.count_hospitals(doctor),
                "id": doctor.id,
                "deal_price": filtered_deal_price,
                "mrp": filtered_mrp,
                "is_live": doctor.is_live,
                "is_gold": False,
                "discounted_fees": filtered_deal_price,
                "practicing_since": doctor.practicing_since,
                "experience_years": doctor.experience_years(),
                "general_specialization": serializers.DoctorPracticeSpecializationSerializer(
                    doctor.doctorpracticespecializations.all(),
                    many=True).data,
                "distance": self.get_distance(doctor, doctor_clinic_mapping),
                "name": doctor.name,
                "display_name": doctor.get_display_name(),
                "gender": doctor.gender,
                "thumbnail": (
                    request.build_absolute_uri(thumbnail) if thumbnail else None),

                "schema": {
                    "name": doctor.get_display_name(),
                    "image": doctor.get_thumbnail() if doctor.get_thumbnail() else static('web/images/doc_placeholder.png'),
                    "@context": 'http://schema.org',
                    "@type": 'MedicalBusiness',
                    "address": {
                        "@type": 'PostalAddress',
                        "addressLocality": doctor_clinic.hospital.locality if doctor_clinic and getattr(doctor_clinic, 'hospital', None) else '',
                        "addressRegion": doctor_clinic.hospital.city if doctor_clinic and getattr(doctor_clinic, 'hospital', None) else '',
                        "postalCode": doctor_clinic.hospital.pin_code if doctor_clinic and getattr(doctor_clinic, 'hospital', None) else '',
                        "streetAddress": doctor_clinic.hospital.get_hos_address() if doctor_clinic and getattr(doctor_clinic, 'hospital', None) else '',
                    },
                    "description": doctor.about,
                    "priceRange": min_price["deal_price"],
                    'openingHours': opening_hours,
                    'location': {
                        '@type': 'Place',
                        'geo': {
                            '@type': 'GeoCircle',
                            'geoMidpoint': {
                                '@type': 'GeoCoordinates',
                                'latitude': doctor_clinic.hospital.location.y if doctor_clinic and
                                                                                 getattr(doctor_clinic, 'hospital', None) and getattr(doctor_clinic.hospital, 'location', None) else None,
                                'longitude': doctor_clinic.hospital.location.x if doctor_clinic and
                                                                                  getattr(doctor_clinic, 'hospital', None) and getattr(doctor_clinic.hospital, 'location', None) else None,
                            }
                        }
                    }

                },
                "url":url


            }

            hospital_id = doctor_clinic.hospital.pk
            if hospital_id:
                if not hospital_card.get('hospital' + str(hospital_id)):
                    hospital_card['hospital' + str(hospital_id)] = hospitals
                    if not hospital_card.get('hospital' + str(hospital_id))[0].get('doctors'):
                        hospital_card.get('hospital' + str(hospital_id))[0]['doctors'] = list()
                    hospital_card['hospital' + str(hospital_id)][0]['doctors'].append(temp)
                else:
                    hospital_card['hospital' + str(hospital_id)][0]['doctors'].append(temp)

        return hospital_card
