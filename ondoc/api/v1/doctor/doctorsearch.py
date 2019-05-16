import operator

from django.contrib.gis.geos import Point
from django.db.models import F

from ondoc.api.v1.doctor.serializers import DoctorProfileUserViewSerializer
from ondoc.api.v1.procedure.serializers import DoctorClinicProcedureSerializer
from ondoc.api.v1.ratings.serializers import GoogleRatingsGraphSerializer
from ondoc.coupon.models import CouponRecommender
from ondoc.doctor import models
from ondoc.api.v1.utils import clinic_convert_timings
from ondoc.api.v1.doctor import serializers
from ondoc.authentication.models import QCModel
from ondoc.doctor.models import Doctor, PracticeSpecialization
from ondoc.procedure.models import DoctorClinicProcedure, ProcedureCategory, ProcedureToCategoryMapping, \
    get_selected_and_other_procedures, get_included_doctor_clinic_procedure, \
    get_procedure_categories_with_procedures
from datetime import datetime
import re
import json
from django.contrib.staticfiles.templatetags.staticfiles import static

from ondoc.location.models import EntityAddress
from collections import OrderedDict
from ondoc.insurance.models import UserInsurance
from collections import defaultdict


class DoctorSearchHelper:
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

        procedure_ids = self.query_params.get("procedure_ids", [])# NEW_LOGIC
        ipd_procedure_ids = self.query_params.get("ipd_procedure_ids", [])
        procedure_category_ids = self.query_params.get("procedure_category_ids", [])  # NEW_LOGIC

        if self.query_params.get('hospital_id') is not None:
            filtering_params.append(
                "h.id=(%(hospital_id)s)")
            params['hospital_id'] = str(self.query_params.get("hospital_id"))

        if self.query_params.get('locality_value'):
            filtering_params.append("h.city_search_key ilike (%(locality_value)s)")
            params['locality_value'] = '%' + self.query_params.get('locality_value').lower() + '%'

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

        if self.query_params.get("sits_at"):
            filtering_params.append(
                "hospital_type IN(%(sits_at)s)"
            )
            params['sits_at'] = ", ".join(
                [str(hospital_type_mapping.get(sits_at)) for sits_at in self.query_params.get("sits_at")])


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


        counter = 1
        if len(ipd_procedure_ids) > 0:
            dcip_str = 'dcip.ipd_procedure_id IN ('
            for id in ipd_procedure_ids:
                if not counter == 1:
                    dcip_str += ','
                dcip_str = dcip_str + '%(' + 'ipd_procedure' + str(counter) + ')s'
                params['ipd_procedure' + str(counter)] = id
                counter += 1
            filtering_params.append(
                dcip_str + ')'
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
                'dl.id is NULL and dct.day=(%(current_time)s) and dct.end>=(%(current_hour)s)')
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
            filtering_params.append("(d.search_key like (%(doctor_name1)s) "
                                    "or d.search_key like  %(doctor_name2)s "
                                    "or d.search_key like %(doctor_name3)s) ")
            # filtering_params.append(
            #     "d.search_key ilike (%(doctor_name)s)"
            #         )
            # params['doctor_name'] = '%'+search_key+'%'
            params['order_doctor'] = search_key
            params['doctor_name1'] = search_key + ' %'
            params['doctor_name2'] = '% ' + search_key + ' %'
            params['doctor_name3'] = '% ' + search_key

        if self.query_params.get("hospital_name"):
            search_key = re.findall(r'[a-z0-9A-Z.]+', self.query_params.get("hospital_name"))
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            filtering_params.append(
                "h.search_key ilike (%(hospital_name)s)")
            params['hospital_name'] = '%' + search_key + '%'

        if self.query_params.get('is_insurance'):
            filtering_params.append(
                "mrp<=(%(insurance_threshold_amount)s) and h.enabled_for_online_booking=True and h.enabled_for_prepaid and d.enabled_for_online_booking=True and d.is_insurance_enabled and dc.enabled_for_online_booking=True"
            )
            params['insurance_threshold_amount'] = self.query_params.get('insurance_threshold_amount')

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
        # order_by_field = 'is_gold desc, distance, dc.priority desc'
        # rank_by = "rank_distance=1"
        if self.query_params and self.query_params.get('doctor_name'):
             return ' enabled_for_online_booking DESC, position(%(order_doctor)s in search_key) ', ' rnk=1'

        if self.query_params.get('url') and (not self.query_params.get('sort_on') \
                                             or self.query_params.get('sort_on')=='distance'):
            return ' enabled_for_online_booking DESC, distance, priority desc ', ' rnk=1 '

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
            order_by_field = "{}, {} ".format(' enabled_for_online_booking DESC ', order_by_field)
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
                order_by_field = ' welcome_calling_done DESC, floor(distance/{bucket_size}) ASC, is_license_verified DESC, search_score desc '.format(bucket_size=str(bucket_size))
                rank_by = "rnk=1"

            order_by_field = "{}, {} ".format(' enabled_for_online_booking DESC ', order_by_field)

        return order_by_field, rank_by

    def prepare_raw_query(self, filtering_params, order_by_field, rank_by):
        longitude = str(self.query_params["longitude"])
        latitude = str(self.query_params["latitude"])
        ist_time = datetime.now().strftime("%H:%M:%S")
        ist_date = datetime.now().strftime("%Y-%m-%d")
        max_distance=None

        if not self.query_params.get('max_distance') == None and self.query_params.get('max_distance')*1000 == 0:
            max_distance = self.query_params.get('max_distance')
        else:
            # max_distance = str(
            #     self.query_params.get('max_distance') * 1000 if self.query_params.get(
            #         'max_distance') and self.query_params.get(
            #         'max_distance') * 1000 < int(DoctorSearchHelper.MAX_DISTANCE) else DoctorSearchHelper.MAX_DISTANCE)
            max_distance = str(
                     self.query_params.get('max_distance') * 1000 if self.query_params.get(
                        'max_distance') and self.query_params.get( 'max_distance') * 1000 else -1)
        min_distance = self.query_params.get('min_distance')*1000 if self.query_params.get('min_distance') else 0

        if self.query_params and self.query_params.get('sitemap_identifier') and self.query_params.get('max_distance')==None:
            sitemap_identifier = self.query_params.get('sitemap_identifier')
            if sitemap_identifier in ('SPECIALIZATION_LOCALITY_CITY', 'DOCTORS_LOCALITY_CITY'):
                max_distance = 3000
            if sitemap_identifier in ('SPECIALIZATION_CITY', 'DOCTORS_CITY'):
                max_distance = 15000

        # max_distance = 10000000000000000000000
        data = dict()

        specialization_ids = self.query_params.get("specialization_ids", [])
        condition_ids = self.query_params.get("condition_ids", [])

        if filtering_params.get('params', {}).get('hospital_id'):
            max_distance = 10000000
            min_distance = 0

        if self.count_of_procedure:
            rank_part = "Row_number() OVER( PARTITION BY doctor_id ORDER BY " \
                           "distance, total_price ASC) rnk "
            if self.query_params.get('sort_on') == 'fees':
                rank_part = " Row_number() OVER( partition BY doctor_id " \
                            "ORDER BY total_price ASC, distance) rnk " \

            query_string = "SELECT doctor_id, hospital_id, doctor_clinic_id, doctor_clinic_timing_id " \
                           "FROM (SELECT total_price, " \
                           " {rank_part} ," \
                           " distance, enabled_for_online_booking, is_license_verified, welcome_calling_done, priority " \
                           "procedure_deal_price, doctor_id, practicing_since, doctor_clinic_id, doctor_clinic_timing_id, " \
                           "procedure_id, doctor_clinic_deal_price, hospital_id " \
                           "FROM (SELECT distance, procedure_deal_price, doctor_id, practicing_since, doctor_clinic_id, doctor_clinic_timing_id, procedure_id," \
                           "enabled_for_online_booking, is_license_verified, welcome_calling_done, priority, " \
                           "doctor_clinic_deal_price, hospital_id , count_per_clinic, sum_per_clinic, sum_per_clinic+doctor_clinic_deal_price as total_price FROM " \
                           "(SELECT " \
                           "COUNT(procedure_id) OVER (PARTITION BY dct.id) AS count_per_clinic, " \
                           "SUM(dcp.deal_price) OVER (PARTITION BY dct.id) AS sum_per_clinic, " \
                           "St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location) AS distance, " \
                           "dcp.deal_price AS procedure_deal_price, h.welcome_calling_done,  " \
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
                           "case when (%(max_distance)s) >= 0  then St_dwithin( St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location, (%(max_distance)s))" \
                           " else St_dwithin( St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location, h.search_distance ) end AND " \
                           "St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location, (%(min_distance)s)) = false " \
                           " ) " \
                           "AS tempTable WHERE count_per_clinic={count_of_procedure}) AS tempTable2) " \
                           "x WHERE {rank_by} ORDER BY {order_by_field}".format(
                rank_part = rank_part, filtering_params=filtering_params.get('string'),
                count_of_procedure=filtering_params.get('count_of_procedure'),
                rank_by=rank_by, order_by_field=order_by_field)

        else:
            sp_cond = ''
            min_dist_cond = ''
            rank_part = " Row_number() OVER( partition BY d.id  ORDER BY " \
                "St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location),dct.deal_price ASC) rnk " \

            if len(specialization_ids)>0 or len(condition_ids)>0:
                sp_cond = " LEFT JOIN doctor_practice_specialization ds on ds.doctor_id = d.id " \
                       " LEFT JOIN practice_specialization gs on ds.specialization_id = gs.id "
            if min_distance>0:
                min_dist_cond = " and St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location, (%(min_distance)s)) = false "

            if self.query_params.get('sort_on') == 'fees':
                rank_part = " Row_number() OVER( partition BY d.id  ORDER BY " \
                            "dct.deal_price, St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location) ASC) rnk " \

            if self.query_params and self.query_params.get("ipd_procedure_ids"):
                ipd_query = " INNER JOIN doctor_clinic_ipd_procedure dcip on dc.id = dcip.doctor_clinic_id " \
                            " AND dcip.enabled=True "
            else:
                ipd_query = ""

            query_string = "SELECT x.doctor_id, x.hospital_id, doctor_clinic_id, doctor_clinic_timing_id " \
                           "FROM (select {rank_part}, " \
                           "St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location) distance, " \
                           "d.id as doctor_id, " \
                           "dc.id as doctor_clinic_id,  d.search_key, " \
                           "dct.id as doctor_clinic_timing_id,practicing_since, " \
                           "d.enabled_for_online_booking and dc.enabled_for_online_booking and h.enabled_for_online_booking as enabled_for_online_booking, " \
                           "is_license_verified, priority,deal_price, h.welcome_calling_done, " \
                           "dc.hospital_id as hospital_id, d.search_score FROM doctor d " \
                           "INNER JOIN doctor_clinic dc ON d.id = dc.doctor_id and dc.enabled=true and d.is_live=true " \
                           "and d.is_test_doctor is False and d.is_internal is False " \
                           "INNER JOIN hospital h ON h.id = dc.hospital_id and h.is_live=true " \
                           "INNER JOIN doctor_clinic_timing dct ON dc.id = dct.doctor_clinic_id " \
                           "{ipd_query} " \
                           "LEFT JOIN doctor_leave dl on dl.doctor_id = d.id and (%(ist_date)s) BETWEEN dl.start_date and dl.end_date " \
                           "AND (%(ist_time)s) BETWEEN dl.start_time and dl.end_time " \
                           "{sp_cond} " \
                           "WHERE {filtering_params} " \
                           "and case when (%(max_distance)s) >= 0  then St_dwithin( St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location, (%(max_distance)s))" \
                           " else St_dwithin( St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location, h.search_distance ) end" \
                           "{min_dist_cond}" \
                           " )x " \
                           "where {rank_by} ORDER BY {order_by_field}".format(rank_part=rank_part, sp_cond=sp_cond, \
                                                                              filtering_params=filtering_params.get(
                                                                                  'string'), \
                                                                              min_dist_cond=min_dist_cond,
                                                                              order_by_field=order_by_field, \
                                                                              rank_by=rank_by, ipd_query=ipd_query)

        if filtering_params.get('params'):
            filtering_params.get('params')['longitude'] = longitude
            filtering_params.get('params')['latitude'] = latitude
            filtering_params.get('params')['min_distance'] = min_distance
            filtering_params.get('params')['max_distance'] = max_distance
            filtering_params.get('params')['ist_time'] = ist_time
            filtering_params.get('params')['ist_date'] = ist_date
        else:
            filtering_params['params']['longitude'] = longitude
            filtering_params['params']['latitude'] = latitude
            filtering_params['params']['min_distance'] = min_distance
            filtering_params['params']['max_distance'] = max_distance
            filtering_params.get('params')['ist_time'] = ist_time
            filtering_params.get('params')['ist_date'] = ist_date

        return {'params':filtering_params.get('params'), 'query': query_string}

    def count_hospitals(self, doctor):
        return len([h for h in doctor.hospitals.all() if h.is_live == True])

    def get_distance(self, doctor, doctor_clinic_mapping):
        current_location = Point(self.query_params.get("longitude"), self.query_params.get("latitude"),
                                srid=4326)
        for hospital in doctor.hospitals.all():
            if hospital.id == doctor_clinic_mapping[doctor.id] and hospital.location:
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

    def prepare_search_response(self, doctor_data, doctor_search_result, request, **kwargs):
        query_params = self.query_params

        doctor_clinic_mapping = {data.get("doctor_id"): data.get("hospital_id") for data in doctor_search_result}
        doctor_availability_mapping = {data.get("doctor_id"): data.get("doctor_clinic_timing_id") for data in
                                       doctor_search_result}
        category_ids = query_params.get("procedure_category_ids", [])
        procedure_ids = query_params.get("procedure_ids", [])
        category_ids = [int(x) for x in category_ids]
        procedure_ids = [int(x) for x in procedure_ids]
        response = []
        specialization_ids = query_params.get('specialization_ids', [])
        selected_procedure_ids, other_procedure_ids = get_selected_and_other_procedures(category_ids, procedure_ids)
        profile = query_params.get("profile_id", None)
        product_id = query_params.get("product_id", None)
        coupon_code = query_params.get("coupon_code", None)

        coupon_recommender = CouponRecommender(request.user, profile, 'doctor', product_id, coupon_code, None)
        filters = dict()

        for doctor in doctor_data:
            enable_online_booking = False
            should_apply_coupon = False

            is_gold = False #doctor.enabled_for_online_booking and doctor.is_gold
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

                if doctor_clinic and doctor and doctor_clinic.hospital:
                    if doctor.enabled_for_online_booking and doctor_clinic.hospital.enabled_for_online_booking and doctor_clinic.enabled_for_online_booking:
                        enable_online_booking = True
                        if doctor_clinic.hospital.enabled_for_prepaid:
                            should_apply_coupon = True

                # We cover the insurance for only those users which have purchased the insurance and their insurance
                # threshold value is greater than the doctor fees and if doctor is enabled for the online booking.
                # Insurance is not valid for the procedures hence negating the procedure request.

                is_insurance_covered = False
                insurance_data_dict = kwargs.get('insurance_data')
                if doctor_clinic.hospital.enabled_for_prepaid and enable_online_booking and doctor.is_insurance_enabled and doctor.is_doctor_specialization_insured() and insurance_data_dict and min_price.get("mrp") is not None and \
                        min_price["mrp"] <= insurance_data_dict['insurance_threshold_amount'] and \
                        not (request.query_params.get('procedure_ids') or request.query_params.get('procedure_category_ids')):
                    is_insurance_covered = True

                hospitals = [{
                    "enabled_for_online_booking": enable_online_booking,
                    "is_insurance_covered": is_insurance_covered,
                    "insurance_threshold_amount": insurance_data_dict['insurance_threshold_amount'],
                    "is_user_insured": insurance_data_dict['is_user_insured'],
                    "welcome_calling_done": doctor_clinic.hospital.welcome_calling_done,
                    "hospital_name": doctor_clinic.hospital.name,
                    "address": ", ".join(
                        [value for value in [doctor_clinic.hospital.sublocality, doctor_clinic.hospital.locality] if
                         value]),
                    "short_address": doctor_clinic.hospital.get_short_address(),
                    "doctor": doctor.name,
                    "enabled_for_cod": doctor_clinic.hospital.enabled_for_cod,
                    "enabled_for_prepaid": doctor_clinic.hospital.enabled_for_prepaid,
                    "display_name": doctor.get_display_name(),
                    "hospital_id": doctor_clinic.hospital.id,
                    "mrp": min_price["mrp"],
                    "discounted_fees": min_price["deal_price"],
                    "timings": clinic_convert_timings(doctor_clinic.availability.all(), is_day_human_readable=False),
                    "procedure_categories": final_result,
                    "location": {'lat': doctor_clinic.hospital.location.y,
                                 'long': doctor_clinic.hospital.location.x} if doctor_clinic.hospital and doctor_clinic.hospital.location else None,
                    "url": kwargs.get('hosp_entity_dict', {}).get(doctor_clinic.hospital.id),
                    "locality_url": kwargs.get('hosp_locality_entity_dict', {}).get(doctor_clinic.hospital.id)
                }]

            thumbnail = doctor.get_thumbnail()
            
            sorted_spec_list = []
            doctor_spec_list = []
            searched_spec_list = []
            general_specialization = []
            doctor_specializations = []
            
            for dps in doctor.doctorpracticespecializations.all():
                general_specialization.append(dps.specialization)
                doctor_specializations.append(dps.specialization_id)

            general_specialization = sorted(general_specialization, key=operator.attrgetter('doctor_count'), reverse=True)
            for spec in general_specialization:
                if str(spec.id) in specialization_ids:
                    searched_spec_list.append({'name': spec.name})
                else:    
                    doctor_spec_list.append({'name':spec.name})

            sorted_spec_list = searched_spec_list + doctor_spec_list

            opening_hours = None
            if doctor_clinic.availability.exists():
                opening_hours = '%.2f-%.2f' % (doctor_clinic.availability.all()[0].start,
                                                   doctor_clinic.availability.all()[0].end),

            from ondoc.coupon.models import Coupon
            from ondoc.authentication import models as auth_model

            search_coupon = None
            if should_apply_coupon:
                # search_coupon = Coupon.get_search_coupon(request.user)
                filters['deal_price'] = filtered_deal_price
                filters['doctor_id'] = doctor.id
                filters['doctor_specializations_ids'] = doctor_specializations
                filters['hospital'] = doctor_clinic.hospital
                search_coupon = coupon_recommender.best_coupon(**filters)

            discounted_price = filtered_deal_price if not search_coupon else search_coupon.get_search_coupon_discounted_price(filtered_deal_price)
            schema_specialization = None
            schema_specialization = sorted_spec_list[0].get('name') if sorted_spec_list and len(sorted_spec_list)>0 and sorted_spec_list[0].get('name') else None
            schema_type = None
            new_schema = OrderedDict()
            average_rating = None
            rating_count = None
            google_rating = None
            if schema_specialization == 'Dentist':
                schema_type = 'Dentist'
            else:
                schema_type = 'Physician'

            if doctor.rating_data and doctor.rating_data.get('rating_count')>0:
                if doctor.rating_data.get('rating_count')<5:
                    if doctor.rating_data.get('avg_rating') >=4:
                        average_rating = doctor.rating_data.get('avg_rating')
                        rating_count = doctor.rating_data.get('rating_count')
                else:
                    average_rating = doctor.rating_data.get('avg_rating')
                    rating_count = doctor.rating_data.get('rating_count')
            if not average_rating:
                 if doctor_clinic and doctor_clinic.hospital:
                    hosp_reviews = doctor_clinic.hospital.hospital_place_details.all()
                    if hosp_reviews:
                        reviews_data = hosp_reviews[0].reviews

                        if reviews_data:
                            ratings_graph = GoogleRatingsGraphSerializer(reviews_data, many=False,
                                                                         context={"request": request})
                            google_rating = ratings_graph.data

            temp = {
                "doctor_id": doctor.id,
                "enabled_for_online_booking": doctor.enabled_for_online_booking,
                "is_license_verified" : doctor.is_license_verified and enable_online_booking,
                #"verified": True if doctor.is_license_verified and doctor.enabled_for_online_booking else False,
                "hospital_count": self.count_hospitals(doctor),
                "id": doctor.id,
                "deal_price": filtered_deal_price,
                "mrp": filtered_mrp,
                "is_live": doctor.is_live,
                "is_gold": is_gold,
                # "fees": filtered_fees,*********show mrp here
                "discounted_fees": filtered_deal_price,
                "discounted_price": discounted_price,
                # "discounted_fees": filtered_fees, **********deal_price
                "practicing_since": doctor.practicing_since,
                "experience_years": doctor.experience_years(),
                #"experiences": serializers.DoctorExperienceSerializer(doctor.experiences.all(), many=True).data,
                "qualifications": serializers.DoctorQualificationSerializer(doctor.qualifications.all(), many=True).data,
                # "average_rating": doctor.avg_rating,
                # "average_rating": doctor.rating_data.get('avg_rating') if doctor.rating_data else None,
                # "rating_count": doctor.rating_data.get('rating_count') if doctor.rating_data else None,
                "average_rating": average_rating,
                "rating_count": rating_count,
                "google_rating": google_rating,
                # "general_specialization": serializers.DoctorPracticeSpecializationSerializer(
                #     doctor.doctorpracticespecializations.all(),
                #     many=True).data,
                "general_specialization": sorted_spec_list,
                "distance": self.get_distance(doctor, doctor_clinic_mapping),
                "name": doctor.name,
                "display_name": doctor.get_display_name(),
                "gender": doctor.gender,
                #"images": serializers.DoctorImageSerializer(doctor.images.all(), many=True, context={"request": request}).data,
                "hospitals": hospitals,
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
                                                                                 getattr(doctor_clinic, 'hospital',
                                                                                         None) and getattr(
                                    doctor_clinic.hospital, 'location', None) else None,
                                'longitude': doctor_clinic.hospital.location.x if doctor_clinic and
                                                                                  getattr(doctor_clinic, 'hospital',
                                                                                          None) and getattr(
                                    doctor_clinic.hospital, 'location', None) else None,
                            }
                        }
                    }

                }

            }


            new_schema["@context"] = 'http://schema.org'
            new_schema["@type"] = schema_type
            new_schema["name"] = doctor.get_display_name()
            new_schema["image"] = doctor.get_thumbnail() if doctor.get_thumbnail() else static(
                'web/images/doc_placeholder.png')
            new_schema["url"] = None
            new_schema["medicalSpecialty"] = [schema_specialization]
            new_schema["currenciesAccepted"] = "INR"
            new_schema["priceRange"] = min_price["deal_price"]
            new_schema["address"] = {
                                        "@type": 'PostalAddress',
                                        "addressLocality": doctor_clinic.hospital.locality if doctor_clinic and getattr(
                                            doctor_clinic, 'hospital', None) else '',
                                        "addressRegion": doctor_clinic.hospital.city if doctor_clinic and getattr(
                                            doctor_clinic, 'hospital', None) else '',
                                        # "postalCode": doctor_clinic.hospital.pin_code if doctor_clinic and getattr(doctor_clinic, 'hospital', None) else '',
                                        # "streetAddress": doctor_clinic.hospital.get_hos_address() if doctor_clinic and getattr(doctor_clinic, 'hospital', None) else '',
                                    }
            new_schema['location'] = {
                                         '@type': 'Place',
                                         'geo': {
                                             '@type': 'GeoCoordinates',
                                             'latitude': doctor_clinic.hospital.location.y if doctor_clinic and
                                                                                              getattr(doctor_clinic,
                                                                                                      'hospital',
                                                                                                      None) and getattr(
                                                 doctor_clinic.hospital, 'location', None) else None,
                                             'longitude': doctor_clinic.hospital.location.x if doctor_clinic and
                                                                                               getattr(doctor_clinic,
                                                                                                       'hospital',
                                                                                                       None) and getattr(
                                                 doctor_clinic.hospital, 'location', None) else None,

                                         }
                                     }
            new_schema["branchOf"] = [
                {
                    "@type": "MedicalClinic",
                    "name": doctor_clinic.hospital.name,
                    "priceRange": min_price["deal_price"],
                    "image": doctor_clinic.hospital.get_thumbnail() if doctor_clinic.hospital.get_thumbnail() else None,
                    "address":
                        {
                            "@type": 'PostalAddress',
                            "addressLocality": doctor_clinic.hospital.locality if doctor_clinic and getattr(
                                doctor_clinic, 'hospital', None) else '',
                            "addressRegion": doctor_clinic.hospital.city if doctor_clinic and getattr(
                                doctor_clinic, 'hospital', None) else '',

                        }

                }
            ]

            temp['new_schema'] = new_schema
            response.append(temp)
        return response
