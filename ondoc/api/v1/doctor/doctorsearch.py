from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.gis.geos import Point
from ondoc.doctor import models
from ondoc.api.v1.utils import convert_timings
from ondoc.api.v1.doctor import serializers
from datetime import datetime


class DoctorSearchHelper:
    MAX_DISTANCE = "20000"

    def __init__(self, query_params):
        self.query_params = query_params

    def get_filtering_params(self):
        """Helper function that prepare dynamic query for filtering"""
        hospital_type_mapping = {hospital_type[1]: hospital_type[0] for hospital_type in
                                 models.Hospital.HOSPITAL_TYPE_CHOICES}

        filtering_params = []
        if self.query_params.get("specialization_ids"):
            filtering_params.append(
                "sp.id IN({})".format(",".join(self.query_params.get("specialization_ids")))
            )
        if self.query_params.get("sits_at"):
            filtering_params.append(
                "hospital_type IN({})".format(", ".join([str(hospital_type_mapping.get(sits_at)) for sits_at in
                                                         self.query_params.get("sits_at")]))
            )
        if self.query_params.get("min_fees"):
            filtering_params.append(
                "fees>={}".format(str(self.query_params.get("min_fees"))))
        if self.query_params.get("max_fees"):
            filtering_params.append(
                "fees<={}".format(str(self.query_params.get("max_fees"))))
        if self.query_params.get("is_female"):
            filtering_params.append(
                "gender='f'"
            )
        if self.query_params.get("is_available"):
            current_time = datetime.now()
            current_hour = round(float(current_time.hour) + (float(current_time.minute)*1/60), 2)
            filtering_params.append(
                'dh.day={} and dh.end>={}'.format(str(current_time.weekday()), str(current_hour))
            )
        if self.query_params.get("doctor_name"):
            filtering_params.append(
                "d.name ilike '%{}%'".format(self.query_params.get("doctor_name")))
        if self.query_params.get("hospital_name"):
            filtering_params.append(
                "h.name ilike '%{}%'".format(self.query_params.get("hospital_name")))

        if not filtering_params:
            return "1=1"
        return " and ".join(filtering_params)

    def get_ordering_params(self):
        order_by_field = 'distance'
        rank_by = "rank_distance=1"
        if self.query_params.get('sort_on'):
            if self.query_params.get('sort_on') == 'experience':
                order_by_field = 'practicing_since'
            if self.query_params.get('sort_on') == 'fees':
                order_by_field = "fees"
                rank_by = "rank_fees=1"
        return order_by_field, rank_by

    def prepare_raw_query(self, filtering_params, order_by_field, rank_by):
        longitude = str(self.query_params["longitude"])
        latitude = str(self.query_params["latitude"])
        query_string = "SELECT x.doctor_id, x.hospital_id " \
                       "FROM (SELECT Row_number() OVER( partition BY dh.doctor_id ORDER BY dh.fees ASC) rank_fees, " \
                       "Row_number() OVER( partition BY dh.doctor_id ORDER BY " \
                       "St_distance(St_setsrid(St_point(%s, %s), 4326 ), h.location) ASC) rank_distance, " \
                       "St_distance(St_setsrid(St_point(%s, %s), 4326), h.location) distance, d.id as doctor_id, " \
                       "dh.hospital_id as hospital_id FROM   doctor d " \
                       "INNER JOIN doctor_hospital dh " \
                       "ON d.id = dh.doctor_id " \
                       "INNER JOIN hospital h " \
                       "ON h.id = dh.hospital_id " \
                       "LEFT JOIN doctor_qualification dq " \
                       "ON dq.doctor_id = d.id " \
                       "LEFT JOIN specialization sp " \
                       "ON sp.id = dq.specialization_id " \
                       "WHERE  %s " \
                       "ORDER  BY %s ASC) x " \
                       "where distance < %s and %s" % (longitude, latitude,
                                                       longitude, latitude,
                                                       filtering_params, order_by_field,
                                                       DoctorSearchHelper.MAX_DISTANCE, rank_by)
        return query_string

    def count_hospitals(self, doctor):
        hospital_count = 0
        prev = None
        for dh in doctor.availability.all():
            if dh.hospital_id != prev:
                hospital_count += 1
            prev = dh.hospital_id
        return hospital_count

    def get_distance(self, doctor, doctor_hospital_mapping):
        current_location = Point(self.query_params.get("longitude"), self.query_params.get("latitude"),
                                srid=4326)
        for hospital in doctor.hospitals.all():
            if hospital.id == doctor_hospital_mapping[doctor.id]:
                return current_location.distance(hospital.location)*100*1000
        return ""

    def prepare_search_response(self, doctor_data, doctor_search_result, request):
        doctor_hospital_mapping = {data.get("doctor_id"): data.get("hospital_id") for data in doctor_search_result}
        response = []
        for doctor in doctor_data:
            doctor_hospitals = [doctor_hospital for doctor_hospital in doctor.availability.all() if
                                doctor_hospital.hospital_id == doctor_hospital_mapping[doctor_hospital.doctor_id]]
            serializer = serializers.DoctorHospitalSerializer(doctor_hospitals, many=True)

            if not serializer.data:
                hospitals = []
            else:
                hospitals = [{
                    "hospital_name": serializer.data[0]["hospital_name"],
                    "address": serializer.data[0]["address"],
                    "doctor": serializer.data[0]["doctor"],
                    "hospital_id": serializer.data[0]['hospital_id'],
                    "fees": serializer.data[0]["fees"],
                    "discounted_fees": serializer.data[0]["discounted_fees"],
                    "timings": convert_timings(serializer.data, is_day_human_readable=True)
                }]
            temp = {
                "doctor_id": doctor.id,
                "hospital_count": self.count_hospitals(doctor),
                "id": doctor.id,
                "practicing_since": doctor.practicing_since,
                "experience_years": None,
                "experiences": serializers.DoctorExperienceSerializer(doctor.experiences.all(), many=True).data,
                "qualifications": serializers.DoctorQualificationSerializer(doctor.qualifications.all(),
                                                                            many=True).data,
                "distance": self.get_distance(doctor, doctor_hospital_mapping),
                "name": doctor.name,
                "gender": doctor.gender,
                "images": serializers.DoctorImageSerializer(doctor.images.all(), many=True,
                                                            context={"request": request}).data,
                "hospitals": hospitals,
                "thumbnail": (
                    request.build_absolute_uri(
                        static('doctor_images/no_image.png')) if not doctor.images.all() else request.build_absolute_uri(
                        doctor.images.all()[0].name.url))
            }
            response.append(temp)
        return response
