from django.contrib.gis.geos import Point
from django.db.models import F

from ondoc.api.v1.doctor.serializers import DoctorProfileUserViewSerializer
from ondoc.api.v1.procedure.serializers import DoctorClinicProcedureSerializer
from ondoc.doctor import models
from ondoc.api.v1.utils import clinic_convert_timings
from ondoc.api.v1.doctor import serializers
from ondoc.authentication.models import QCModel
from ondoc.doctor.models import Doctor
from ondoc.procedure.models import DoctorClinicProcedure, ProcedureCategory, ProcedureToCategoryMapping, \
    get_selected_and_other_procedures, get_included_doctor_clinic_procedure, \
    get_procedure_categories_with_procedures
from datetime import datetime
import re
import json
from django.contrib.staticfiles.templatetags.staticfiles import static

from ondoc.location.models import EntityAddress
from collections import OrderedDict
from collections import defaultdict


class DoctorSearchHelper:
    MAX_DISTANCE = "20000"

    def __init__(self, query_params):
        self.query_params = query_params

    def get_filtering_params(self):
        """Helper function that prepare dynamic query for filtering"""
        params = {}
        hospital_type_mapping = {hospital_type[1]: hospital_type[0] for hospital_type in
                                 models.Hospital.HOSPITAL_TYPE_CHOICES}

        filtering_params = ['d.is_test_doctor is False',
                            'd.is_internal is False']

        specialization_ids = self.query_params.get("specialization_ids", [])
        condition_ids = self.query_params.get("condition_ids", [])
        if len(condition_ids)>0:
            cs = list(models.MedicalConditionSpecialization.objects.filter(medical_condition_id__in=condition_ids).values_list('specialization_id', flat=True));
            cs = [str(i) for i in cs]
            specialization_ids.extend(cs)

        # " gs.id IN({})".format(",".join(specialization_ids))

        counter=1
        if len(specialization_ids) > 0:
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
            params['sits_at'] = ", ".join([str(hospital_type_mapping.get(sits_at)) for sits_at in self.query_params.get("sits_at")])

        procedure_ids = self.query_params.get("procedure_ids", [])  # NEW_LOGIC
        procedure_category_ids = self.query_params.get("procedure_category_ids", [])  # NEW_LOGIC

        procedure_mapped_ids = []  # NEW_LOGIC

        if procedure_category_ids and not procedure_ids:  # NEW_LOGIC
            preferred_procedure_ids = list(
                ProcedureCategory.objects.filter(pk__in=procedure_category_ids, is_live=True).values_list(
                    'preferred_procedure_id', flat=True))
            procedure_ids = preferred_procedure_ids

        if len(procedure_ids) > 0:  # NEW_LOGIC
            ps = list(procedure_ids)
            ps = [str(i) for i in ps]
            procedure_mapped_ids.extend(ps)
            filtering_params.append(
                " dcp.procedure_id IN({})".format(",".join(procedure_mapped_ids)))

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
            search_key = re.findall(r'[a-z0-9A-Z.]+', self.query_params.get("doctor_name"))
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

        if not filtering_params:
            return "1=1"
        result = {}
        result['string'] = " and ".join(filtering_params)
        result['params'] = params
        return result

    def get_ordering_params(self):
        order_by_field = 'is_gold desc, distance, dc.priority desc'
        rank_by = "rank_distance=1"

        if self.query_params.get('url') and not self.query_params.get('sort_on'):
            return 'distance, dc.priority desc', rank_by

        if self.query_params.get("procedure_ids", []) or self.query_params.get("procedure_category_ids", []):  # NEW_LOGIC
            order_by_field = 'count_per_clinic desc, distance, sum_per_clinic'  # NEW_LOGIC
            rank_by = "rank_procedure=1"
            if self.query_params.get('sort_on'):
                if self.query_params.get('sort_on') == 'experience':
                    order_by_field = 'practicing_since ASC'
                if self.query_params.get('sort_on') == 'fees':
                    order_by_field = "count_per_clinic DESC, sum_per_clinic ASC, distance ASC"
                    rank_by = "rank_fees=1"
            order_by_field = "{} ".format(order_by_field)
        else:
            if self.query_params.get('sort_on'):
                if self.query_params.get('sort_on') == 'experience':
                    order_by_field = 'practicing_since ASC, dc.priority desc'
                if self.query_params.get('sort_on') == 'fees':
                    order_by_field = "deal_price ASC, dc.priority desc"
                    rank_by = "rank_fees=1"
            order_by_field = "{}, {} ".format('d.is_live DESC, d.enabled_for_online_booking DESC, d.is_license_verified DESC', order_by_field)

        return order_by_field, rank_by

    def prepare_raw_query(self, filtering_params, order_by_field, rank_by):
        longitude = str(self.query_params["longitude"])
        latitude = str(self.query_params["latitude"])
        max_distance = str(
            self.query_params.get('max_distance') * 1000 if self.query_params.get(
                'max_distance') and self.query_params.get(
                'max_distance') * 1000 < int(DoctorSearchHelper.MAX_DISTANCE) else DoctorSearchHelper.MAX_DISTANCE)
        min_distance = self.query_params.get('min_distance')*1000 if self.query_params.get('min_distance') else 0
        # max_distance = 10000000000000000000000
        data = dict()

        if self.query_params.get("procedure_ids", []) or self.query_params.get("procedure_category_ids", []):  # NEW_LOGIC
            query_string = "SELECT doctor_id, hospital_id, doctor_clinic_id, doctor_clinic_timing_id " \
                           "FROM (SELECT ROW_NUMBER() OVER (PARTITION BY doctor_id ORDER BY count_per_clinic DESC, " \
                           "distance ASC, sum_per_clinic ASC ) AS rank_procedure, " \
                           "count_per_clinic, " \
                           "Row_number() OVER( PARTITION BY doctor_id ORDER BY count_per_clinic DESC, sum_per_clinic ASC, distance ASC) as rank_fees, " \
                           "sum_per_clinic, " \
                           "Row_number() OVER( PARTITION BY doctor_id ORDER BY " \
                           "distance, count_per_clinic DESC, sum_per_clinic ASC) rank_distance, " \
                           "distance, " \
                           "procedure_deal_price, doctor_id, practicing_since, doctor_clinic_id, doctor_clinic_timing_id, " \
                           "procedure_id, doctor_clinic_deal_price, hospital_id " \
                           "FROM (SELECT " \
                           "COUNT(procedure_id) OVER (PARTITION BY dct.id) AS count_per_clinic, " \
                           "SUM(dcp.deal_price) OVER (PARTITION BY dct.id) AS sum_per_clinic, " \
                           "St_distance(St_setsrid(St_point({lng}, {lat}), 4326), h.location) AS distance, " \
                           "dcp.deal_price AS procedure_deal_price, " \
                           "d.id AS doctor_id, practicing_since, " \
                           "dc.id AS doctor_clinic_id,  dct.id AS doctor_clinic_timing_id, dcp.id AS doctor_clinic_procedure_id, " \
                           "dcp.procedure_id, dct.deal_price AS doctor_clinic_deal_price, " \
                           "dc.hospital_id AS hospital_id FROM doctor d " \
                           "INNER JOIN doctor_clinic dc ON d.id = dc.doctor_id " \
                           "INNER JOIN hospital h ON h.id = dc.hospital_id AND h.is_live=true " \
                           "INNER JOIN doctor_clinic_timing dct ON dc.id = dct.doctor_clinic_id " \
                           "INNER JOIN doctor_clinic_procedure dcp ON dc.id = dcp.doctor_clinic_id " \
                           "LEFT JOIN doctor_practice_specialization ds ON ds.doctor_id = d.id " \
                           "LEFT JOIN practice_specialization gs ON ds.specialization_id = gs.id " \
                           "WHERE d.is_live=true AND {fltr_prmts} AND " \
                           "St_distance(St_setsrid(St_point({lng}, {lat}), 4326 ), h.location) < {max_dist} AND " \
                           "St_distance(St_setsrid(St_point({lng}, {lat}), 4326 ), h.location) >= {min_dist} " \
                           "ORDER BY d.is_live DESC, d.enabled_for_online_booking DESC, " \
                           "d.is_license_verified DESC, is_gold desc,  dc.priority desc ) AS tempTable) " \
                           "x WHERE {where_prms} ORDER BY {odr_prm}".format(lng=longitude,
                                                                            lat=latitude,
                                                                            fltr_prmts=filtering_params,
                                                                            max_dist=max_distance,
                                                                            min_dist=min_distance,
                                                                            odr_prm=order_by_field,
                                                                            where_prms=rank_by)

        else:
            query_string = "SELECT x.doctor_id, x.hospital_id, doctor_clinic_id, doctor_clinic_timing_id " \
                       "FROM (SELECT Row_number() OVER( partition BY dc.doctor_id " \
                       "ORDER BY dct.deal_price ASC) rank_fees, " \
                       "Row_number() OVER( partition BY dc.doctor_id  ORDER BY " \
                       "St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location),dct.deal_price ASC) rank_distance, " \
                       "St_distance(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326), h.location) distance, d.id as doctor_id, " \
                       "dc.id as doctor_clinic_id,  " \
                       "dct.id as doctor_clinic_timing_id, " \
                       "dc.hospital_id as hospital_id FROM   doctor d " \
                       "INNER JOIN doctor_clinic dc ON d.id = dc.doctor_id and dc.enabled=true " \
                       "INNER JOIN hospital h ON h.id = dc.hospital_id and h.is_live=true " \
                       "INNER JOIN doctor_clinic_timing dct ON dc.id = dct.doctor_clinic_id " \
                       "LEFT JOIN doctor_practice_specialization ds on ds.doctor_id = d.id " \
                       "LEFT JOIN practice_specialization gs on ds.specialization_id = gs.id " \
                       "WHERE d.is_live=true and {filtering_params} " \
                       "and St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location, (%(max_distance)s))" \
                       "and St_dwithin(St_setsrid(St_point((%(longitude)s), (%(latitude)s)), 4326 ), h.location, (%(min_distance)s)) = false " \
                        "ORDER  BY {order_by_field} ) x " \
                        "where {rank_by}".format(filtering_params=filtering_params.get('string'), order_by_field=order_by_field, rank_by = rank_by)
                       # "ORDER  BY {ordering_field} ) x " \
                       #  "where {rank_field}" % ({'ordering_field': order_by_field, 'rank_field': rank_by})
                       # % (longitude, latitude,
                       #               longitude, latitude,
                       #               filtering_params,
                       #               longitude, latitude, max_distance,
                       #               longitude, latitude, min_distance,
                       #               order_by_field, rank_by)
        if filtering_params.get('params'):
            filtering_params.get('params')['longitude'] = longitude
            filtering_params.get('params')['latitude'] = latitude
            filtering_params.get('params')['min_distance'] = min_distance
            filtering_params.get('params')['max_distance'] = max_distance
        else:
             filtering_params['params']['longitude'] = longitude
             filtering_params['params']['latitude'] = latitude
             filtering_params['params']['min_distance'] = min_distance
             filtering_params['params']['max_distance'] = max_distance

        return {'params':filtering_params.get('params'), 'query': query_string}

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

    def prepare_search_response(self, doctor_data, doctor_search_result, request):
        doctor_clinic_mapping = {data.get("doctor_id"): data.get("hospital_id") for data in doctor_search_result}
        doctor_availability_mapping = {data.get("doctor_id"): data.get("doctor_clinic_timing_id") for data in
                                       doctor_search_result}
        category_ids = self.query_params.get("procedure_category_ids", [])
        procedure_ids = self.query_params.get("procedure_ids", [])
        category_ids = [int(x) for x in category_ids]
        procedure_ids = [int(x) for x in procedure_ids]
        response = []
        selected_procedure_ids, other_procedure_ids = get_selected_and_other_procedures(category_ids, procedure_ids)
        for doctor in doctor_data:

            is_gold = doctor.enabled_for_online_booking and doctor.is_gold
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
                all_doctor_clinic_procedures = list(doctor_clinic.doctorclinicprocedure_set.all())
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
                hospitals = [{
                    "hospital_name": doctor_clinic.hospital.name,
                    "address": ", ".join(
                        [value for value in [doctor_clinic.hospital.sublocality, doctor_clinic.hospital.locality] if
                         value]),
                    "short_address": doctor_clinic.hospital.get_short_address(),
                    "doctor": doctor.name,
                    "display_name": doctor.get_display_name(),
                    "hospital_id": doctor_clinic.hospital.id,
                    "mrp": min_price["mrp"],
                    "discounted_fees": min_price["deal_price"],
                    "timings": clinic_convert_timings(doctor_clinic.availability.all(), is_day_human_readable=False),
                    "procedure_categories": final_result
                }]

            thumbnail = doctor.get_thumbnail()

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
                "is_gold": is_gold,
                # "fees": filtered_fees,*********show mrp here
                "discounted_fees": filtered_deal_price,
                # "discounted_fees": filtered_fees, **********deal_price
                "practicing_since": doctor.practicing_since,
                "experience_years": doctor.experience_years(),
                #"experiences": serializers.DoctorExperienceSerializer(doctor.experiences.all(), many=True).data,
                #"qualifications": serializers.DoctorQualificationSerializer(doctor.qualifications.all(), many=True).data,
                "general_specialization": serializers.DoctorPracticeSpecializationSerializer(
                    doctor.doctorpracticespecializations.all(),
                    many=True).data,
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
                                                                                 getattr(doctor_clinic, 'hospital', None) and getattr(doctor_clinic.hospital, 'location', None) else None,
                                'longitude': doctor_clinic.hospital.location.x if doctor_clinic and
                                                                                  getattr(doctor_clinic, 'hospital', None) and getattr(doctor_clinic.hospital, 'location', None) else None,
                            }
                        }
                    }

                }
            }
            response.append(temp)
        return response
