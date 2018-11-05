from django.contrib.gis.geos import Point
from django.db.models import F

from ondoc.doctor import models
from ondoc.api.v1.utils import clinic_convert_timings
from ondoc.api.v1.doctor import serializers
from django.core import serializers as core_serializer
from ondoc.authentication.models import QCModel
from ondoc.doctor.models import Doctor
from ondoc.procedure.models import DoctorClinicProcedure, ProcedureCategory, ProcedureToCategoryMapping
from datetime import datetime
import re
import json
from ondoc.location.models import EntityAddress


class DoctorSearchHelper:
    MAX_DISTANCE = "20000"

    def __init__(self, query_params):
        self.query_params = query_params

    def get_filtering_params(self):
        """Helper function that prepare dynamic query for filtering"""

        hospital_type_mapping = {hospital_type[1]: hospital_type[0] for hospital_type in
                                 models.Hospital.HOSPITAL_TYPE_CHOICES}

        filtering_params = ['d.is_test_doctor is False',
                            'd.is_internal is False']

        specialization_ids = self.query_params.get("specialization_ids",[])
        condition_ids = self.query_params.get("condition_ids", [])
        procedure_ids = self.query_params.get("procedure_ids", [])
        category_ids = self.query_params.get("procedure_category_ids", [])

        if len(condition_ids)>0:
            cs = list(models.MedicalConditionSpecialization.objects.filter(medical_condition_id__in=condition_ids).values_list('specialization_id', flat=True));
            cs = [str(i) for i in cs]
            specialization_ids.extend(cs)

        if len(specialization_ids)>0:
            filtering_params.append(
                " gs.id IN({})".format(",".join(specialization_ids))
            )

        procedure_mapped_doctor_clinic_ids = []

        if len(category_ids) > 0 and not len(procedure_ids) > 0:
            preferred_procedure_ids = list(
                ProcedureCategory.objects.filter(pk__in=category_ids, is_live=True).values_list('preferred_procedure_id', flat=True))
            procedure_ids = preferred_procedure_ids

        if len(procedure_ids)>0:
            for id in procedure_ids:
                ps = list(DoctorClinicProcedure.objects.filter(procedure_id=id).values_list('doctor_clinic_id',
                                                                                            flat=True).distinct())
                ps = [str(i) for i in ps]
                procedure_mapped_doctor_clinic_ids.extend(ps)
            if len(procedure_mapped_doctor_clinic_ids)>0:
                filtering_params.append(
                    " dc.id IN({})".format(",".join(procedure_mapped_doctor_clinic_ids)))

        if self.query_params.get("sits_at"):
            filtering_params.append(
                "hospital_type IN({})".format(", ".join([str(hospital_type_mapping.get(sits_at)) for sits_at in
                                                         self.query_params.get("sits_at")]))
            )
        if self.query_params.get("min_fees") is not None:
            if not len(procedure_ids)>0:
                filtering_params.append(
                    "dct.deal_price>={}".format(str(self.query_params.get("min_fees"))))
        if self.query_params.get("max_fees") is not None:
            if not len(procedure_ids)>0:
                filtering_params.append(
                    "dct.deal_price<={}".format(str(self.query_params.get("max_fees"))))
        if self.query_params.get("is_female"):
            filtering_params.append(
                "gender='f'"
            )
        if self.query_params.get("is_available"):
            current_time = datetime.now()
            current_hour = round(float(current_time.hour) + (float(current_time.minute)*1/60), 2) + .75
            filtering_params.append(
                'dct.day={} and dct.end>={}'.format(str(current_time.weekday()), str(current_hour))
            )
        if self.query_params.get("doctor_name"):
            search_key = re.findall(r'[a-z0-9A-Z.]+', self.query_params.get("doctor_name"))
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            filtering_params.append(
                "d.search_key ilike '%{}%'".format(search_key))
        if self.query_params.get("hospital_name"):
            search_key = re.findall(r'[a-z0-9A-Z.]+', self.query_params.get("hospital_name"))
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            filtering_params.append(
                "h.search_key ilike '%{}%'".format(search_key))

        if not filtering_params:
            return "1=1"
        return " and ".join(filtering_params)

    def get_ordering_params(self):
        order_by_field = 'is_gold desc, distance'
        rank_by = "rank_distance=1"
        if self.query_params.get('sort_on'):
            if self.query_params.get('sort_on') == 'experience':
                order_by_field = 'practicing_since ASC'
            if self.query_params.get('sort_on') == 'fees':
                order_by_field = "deal_price ASC"
                rank_by = "rank_fees=1"
        order_by_field = "{}, {} ".format('d.is_live DESC, d.enabled_for_online_booking DESC, d.is_license_verified DESC'
                                          , order_by_field)
        # order_by_field = "{}, {} ".format('d.is_live DESC', order_by_field)
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

        query_string = "SELECT x.doctor_id, x.hospital_id, doctor_clinic_id, doctor_clinic_timing_id, " \
                       "doctor_clinic_procedure_id " \
                       "FROM (SELECT Row_number() OVER( partition BY dc.doctor_id " \
                       "ORDER BY dct.deal_price ASC) rank_fees, " \
                       "Row_number() OVER( partition BY dc.doctor_id  ORDER BY " \
                       "St_distance(St_setsrid(St_point(%s, %s), 4326 ), h.location),dct.deal_price ASC) rank_distance, " \
                       "St_distance(St_setsrid(St_point(%s, %s), 4326), h.location) distance, d.id as doctor_id, " \
                       "dc.id as doctor_clinic_id,  " \
                       "dct.id as doctor_clinic_timing_id, " \
                       "dcp.id as doctor_clinic_procedure_id, " \
                       "dc.hospital_id as hospital_id FROM   doctor d " \
                       "INNER JOIN doctor_clinic dc ON d.id = dc.doctor_id " \
                       "INNER JOIN hospital h ON h.id = dc.hospital_id and h.is_live=true " \
                       "INNER JOIN doctor_clinic_timing dct ON dc.id = dct.doctor_clinic_id " \
                       "INNER JOIN doctor_clinic_procedure dcp ON dc.id = dcp.doctor_clinic_id " \
                       "LEFT JOIN doctor_practice_specialization ds on ds.doctor_id = d.id " \
                       "LEFT JOIN practice_specialization gs on ds.specialization_id = gs.id " \
                       "WHERE d.is_live=true and %s " \
                       "and St_distance(St_setsrid(St_point(%s, %s), 4326 ), h.location) < %s" \
                       "and St_distance(St_setsrid(St_point(%s, %s), 4326 ), h.location) >= %s " \
                       "ORDER  BY %s ) x " \
                       "where %s" % (longitude, latitude,
                                     longitude, latitude,
                                     filtering_params,
                                     longitude, latitude, max_distance,
                                     longitude, latitude, min_distance,
                                     order_by_field, rank_by)
        return query_string

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
        response = []
        for doctor in doctor_data:

            is_gold = doctor.enabled_for_online_booking and doctor.is_gold
            doctor_clinics = [doctor_clinic for doctor_clinic in doctor.doctor_clinics.all() if
                              doctor_clinic.hospital_id == doctor_clinic_mapping[doctor_clinic.doctor_id]]
            doctor_clinic = doctor_clinics[0]
            doctor_clinic_procedure = DoctorClinicProcedure.objects.filter(doctor_clinic=doctor_clinic).values(
                'id', 'mrp', 'agreed_price', 'deal_price', 'doctor_clinic_id', 'procedure_id',
                detail=F('procedure__details'), duration=F('procedure__duration'), name=F('procedure__name'))
            # if doctor_clinic_procedure:
            #     procedure_dict = dict()
            #     procedure_list = []
            #     for procedure in doctor_clinic_procedure:
            #         procedure_dict = {"clinic_procedure_id": procedure['id'], "mrp": procedure['mrp'], "agreed_price":
            #                             procedure['agreed_price'], "deal_price": procedure['deal_price'],
            #                             "doctor_clinic_id": procedure['doctor_clinic_id'], "procedure_id":
            #                             procedure['procedure_id'], "procedure_name": procedure['procedure__name'],
            #                             "procedure_details": procedure['procedure__details'], "duration":
            #                             procedure['procedure__duration']}
            #         procedure_list.append(procedure_dict)
            # serializer = serializers.DoctorHospitalSerializer(doctor_clinics, many=True, context={"request": request})
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
                    "procedures": doctor_clinic_procedure
                }]

            thumbnail = doctor.get_thumbnail()

            opening_hours = None
            if doctor_clinic.availability.exists():
                opening_hours = '%.2f-%.2f' % (doctor_clinic.availability.first().start,
                                                   doctor_clinic.availability.first().end),

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
                "experiences": serializers.DoctorExperienceSerializer(doctor.experiences.all(), many=True).data,
                "qualifications": serializers.DoctorQualificationSerializer(doctor.qualifications.all(),
                                                                            many=True).data,
                "general_specialization": serializers.DoctorPracticeSpecializationSerializer(
                    doctor.doctorpracticespecializations.all(),
                    many=True).data,
                "distance": self.get_distance(doctor, doctor_clinic_mapping),
                "name": doctor.name,
                "display_name": doctor.get_display_name(),
                "gender": doctor.gender,
                "images": serializers.DoctorImageSerializer(doctor.images.all(), many=True,
                                                            context={"request": request}).data,
                "hospitals": hospitals,
                "thumbnail": (
                    request.build_absolute_uri(thumbnail) if thumbnail else None),

                "schema": {
                    "name": doctor.get_display_name(),
                    "image": doctor.get_thumbnail() if doctor.get_thumbnail() else '',
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
