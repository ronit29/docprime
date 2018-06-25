from django.utils import timezone
from ondoc.doctor import models
from ondoc.api.v1.utils import convert_timings
from ondoc.api.v1.doctor import serializers


class DoctorSearchHelper:
    MAX_DISTANCE = "10000000000"

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
            current_time = timezone.now()
            filtering_params.append(
                'dh.day={} and dh.end>{}'.format(str(current_time.day), str(current_time.hour))
            )
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

    def prepare_search_response(self, doctor_data, doctor_search_result):
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
                    "hospital_id": serializer.data[0]['hospital_id'],
                    "fees": serializer.data[0]["fees"],
                    "discounted_fees": serializer.data[0]["discounted_fees"],
                    "timings": convert_timings(serializer.data, is_day_human_readable=True)
                }]
            temp = {
                "id": doctor.id,
                "name": doctor.name,
                "experience_years": None,
                "practicing_since": doctor.practicing_since,
                "hospitals": hospitals,
                "experiences": serializers.DoctorExperienceSerializer(doctor.experiences.all(), many=True).data,
                "images": serializers.DoctorImageSerializer(doctor.images.all(), many=True).data,
                "qualifications": serializers.DoctorQualificationSerializer(doctor.qualifications.all(),
                                                                            many=True).data,
                "gender": doctor.gender,

            }
            response.append(temp)
        return response
