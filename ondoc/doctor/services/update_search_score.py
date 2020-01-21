from ondoc.api.v1.ratings.serializers import GoogleRatingsGraphSerializer
from ondoc.common.models import LastUsageTimestamp
from ondoc.doctor import models as doctor_models
from django.db.models import Count, Case, When, F, Prefetch
from ondoc.api.v1.utils import RawSql
import datetime
import logging

from ondoc.doctor.models import DoctorClinic, SearchScoreParams

logger = logging.getLogger(__name__)
from celery import task
from django.db import transaction


class DoctorSearchScore:
    def __init__(self):
        self.scoring_data = { "years_of_experience": [{"min": 0, "max": 5, "score": 0},
                                                          {"min": 5, "max": 10, "score": 2},
                                                          {"min": 10, "max": 15, "score": 4},
                                                          {"min": 15, "max": 20, "score": 6},
                                                          {"min": 20, "max": 25, "score": 8}],

                                 "doctors_in_clinic": [{"min": 0, "max": 5, "score": 0},
                                                        {"min": 5, "max": 10, "score": 1},
                                                        {"min": 10, "max": 20, "score": 3},
                                                        {"min": 20, "max": 40, "score": 6},
                                                        {"min": 40, "max": 60, "score": 7},
                                                        {"min": 60, "max": 80, "score": 8},
                                                        {"min": 80, "max": 100, "score": 9}],
                                 "weightage": [{"popularity_score": 0.20,
                                                "years_of_experience": 0.20,
                                                "doctors_in_clinic": 0.25,
                                                "average_ratings": 0.15,
                                                "ratings_count": 0.15,
                                                "discount": 0.15,
                                                "partner_app_activity": 0.10}],

                                 "average_ratings": [{"min": 0, "max": 3, "score": 0},
                                                        {"min": 3, "max": 3.5, "score": 3},
                                                        {"min": 3.5, "max": 4, "score": 7}],

                                 "ratings_count": [{"min": 0, "max": 5, "score": 0},
                                                        {"min": 5, "max": 10, "score": 3},
                                                        {"min": 10, "max": 15, "score": 7}],

                                 "discount_percentage": [{"min": 1, "max": 10, "score": 2},
                                                        {"min": 10, "max": 20, "score": 4},
                                                        {"min": 20, "max": 30, "score": 6},
                                                        {"min": 30, "max": 40, "score": 8}]

                            }
        self.max_score_dict = dict()
        max_score_obj = SearchScoreParams.objects.filter(is_live=True, is_enabled=True)
        for data in max_score_obj:
            self.max_score_dict[data.param] = data.max_score

        doc_popularity = RawSql("select reference_id id, popularity_score score from source_identifier si inner join doctor_popularity dp on dp.unique_identifier= si.unique_identifier where type = 1 ", []).fetch_all()
        self.popularity_data = dict()
        for dp in doc_popularity:
            self.popularity_data[dp['id']] = dp['score']

    def calculate(self):
        doctors_count = doctor_models.Doctor.objects.all().count()
        count = 0
        while count <= doctors_count:
            try:
                score_obj_list = list()
                doctor_in_hosp_count = dict()
                doctors = doctor_models.Doctor.objects.all().prefetch_related("hospitals", "doctor_clinics",
                                                                              Prefetch('doctor_clinics__hospital',
                                                                                       queryset=DoctorClinic.objects.all().order_by('id')),
                                                                              'doctor_clinics__availability',
                                                                              "doctor_clinics__hospital__hospital__hospital_place_details").order_by('id')[count: count+100]

                hospitals_without_network = doctor_models.Hospital.objects.prefetch_related('assoc_doctors', 'hospital_doctors').filter(
                    network__isnull=True, hospital_doctors__doctor__in=doctors).annotate(doctors_count=Count('assoc_doctors__id'))

                for hosp in hospitals_without_network:
                    doctor_in_hosp_count[hosp.id] = hosp.doctors_count

                hospitals_with_network = doctor_models.Hospital.objects.select_related('network').filter(
                    network__isnull=False , hospital_doctors__doctor__in=doctors).annotate(
                    hosp_network_doctors_count=Count(
                        Case(When(network__isnull=False, then=F('network__assoc_hospitals__assoc_doctors')))))
                for hosp in hospitals_with_network:
                    doctor_in_hosp_count[hosp.id] = hosp.hosp_network_doctors_count

                for doctor in doctors:
                    print("doctor : " + str(doctor.id))
                    # popularity_score = self.get_popularity_score(doctor)
                    years_of_experience_score = self.get_practice_score(doctor).get('experience_score')
                    doctors_in_clinic_score = self.get_doctors_score(doctor_in_hosp_count, doctor).get('doctors_in_clinic_score')
                    avg_ratings_score = self.get_doctor_ratings(doctor).get('avg_ratings_score')
                    ratings_count_score = self.get_doctor_ratings_count(doctor).get('ratings_count')
                    discount_score = self.get_discount(doctor).get('discount_percentage')
                    partner_app_activity_score = self.get_partner_app_activity(doctor)

                    final_score = self.get_final_score(doctor, years_of_experience_score=years_of_experience_score, doctors_in_clinic_score=doctors_in_clinic_score, avg_ratings_score=avg_ratings_score, ratings_count_score=ratings_count_score, discount=discount_score, partner_app_activity_score=partner_app_activity_score).get('final_score')

                    score_obj_list.append(
                        doctor_models.SearchScore(doctor=doctor,
                                                  years_of_experience_score=years_of_experience_score,
                                                  doctors_in_clinic_score=doctors_in_clinic_score,
                                                  avg_ratings_score=avg_ratings_score,
                                                  ratings_count_score=ratings_count_score, partner_app_activity=partner_app_activity_score,
                                                  final_score=final_score))

                bulk_created = doctor_models.SearchScore.objects.bulk_create(score_obj_list)
                if bulk_created:
                    print('success')
                else:
                    print('failure')
                count += 100
            except Exception as e:
                 logger.error("Error in calculating search score - " + str(e))

        return 'successfully inserted.'

    def get_partner_app_activity(self, doctor):
        max_score = self.max_score_dict.get('partner_app_activity')
        if max_score and doctor.doctor_clinics.all():
            doctor_clinic = doctor.doctor_clinics.all()[0]
            hospital = doctor_clinic.hospital.hospital if doctor_clinic.hospital else None
            if hospital.spoc_details.all():
                spoc = hospital.spoc_details.all()[0]
                last_usage_timestamp = LastUsageTimestamp.objects.filter(phone_number=spoc.number)
                if(last_usage_timestamp):
                    if((datetime.datetime.today() - last_usage_timestamp).days >48):
                        return max_score
        return 0

    def get_discount(self, doctor):
        max_score = self.max_score_dict.get('discount')
        discount_percentage = self.scoring_data.get('discount_percentage')
        if max_score and doctor.doctor_clinics.all():
            doctor_clinic = doctor.doctor_clinics.all()[0]
            clinic_time = doctor_clinic.availability.all()[0]
            if clinic_time.fees and clinic_time.deal_price:
                discount = (1-clinic_time.fees/clinic_time.deal_price)*100
                for score in discount_percentage:
                    if (discount == 0):
                        return {'discount_percentage': 0}
                    if discount >= 40:
                        return {'discount_percentage': 10}

                    elif discount >= score.get('min') and discount < score.get('max'):
                        return {'discount_percentage': score.get('score') * max_score}

        return {'discount_percentage': 0}

    def get_doctor_ratings(self, doctor):
        max_score = self.max_score_dict.get('avg_ratings_score')
        average_ratings = self.scoring_data.get('average_ratings')
        if max_score and doctor.avg_rating and doctor.avg_rating >= 1:
            for score in average_ratings:
                if doctor.avg_rating >= 4:
                    return {'avg_ratings_score': max_score}

                elif doctor.avg_rating >= score.get('min') and doctor.avg_rating < score.get('max'):
                    return {'avg_ratings_score': score.get('score')/100 * max_score}
        else:
            if max_score and doctor.hospitals.all():
                hospitals = doctor.hospitals.all()
                google_rating = 0
                for hospital in hospitals:
                    hosp_reviews = hospital.hospital_place_details.all()
                    if hosp_reviews:
                        reviews_data = hosp_reviews[0].reviews

                        if reviews_data:
                            ratings_graph = GoogleRatingsGraphSerializer(reviews_data, many=False).data
                            if ratings_graph.get('avg_rating') and ratings_graph.get('avg_rating') > google_rating:
                                google_rating = ratings_graph.get('avg_rating')
                for score in average_ratings:
                    if google_rating >= 4:
                        return {'avg_ratings_score': max_score}

                    elif google_rating >= score.get('min') and google_rating < score.get('max'):
                        return {'avg_ratings_score': score.get('score')/100 * max_score}
            return {'avg_ratings_score': 0}

    def get_doctor_ratings_count(self, doctor):
        max_score = self.max_score_dict.get('ratings_count_score')
        ratings_count = self.scoring_data.get('ratings_count')
        if max_score and doctor.rating_data and doctor.rating_data.get('rating_count'):
            for score in ratings_count:
                if doctor.rating_data.get('rating_count') >= 15:
                    return {'ratings_count': max_score}

                elif doctor.rating_data.get('rating_count') >= score.get('min') and doctor.rating_data.get('rating_count') < score.get('max'):
                    return {'ratings_count': score.get('score')/100 * max_score}

        return {'ratings_count': 0}

    # def get_popularity_score(self, doctor):
    #     pop_score = self.popularity_data.get(doctor.id)
    #
    #     if not pop_score:
    #         pop_score = 0
    #
    #     # popularity_list = self.scoring_data.get('popularity_score')
    #     # for score in popularity_list:
    #     #     if pop_score == 10:
    #     #         return {'popularity_score': 10}
    #     #
    #     #     elif pop_score >= score.get('min') and pop_score < score.get('max'):
    #     return {'popularity_score': pop_score}

    def get_practice_score(self, doctor):
        max_score = self.max_score_dict.get('years_of_experience_score')
        if max_score and doctor.practicing_since:
            years_of_experience = datetime.datetime.now().year - doctor.practicing_since
            exp_years = self.scoring_data.get('years_of_experience')
            for score in exp_years:
                if years_of_experience>=25:
                    return {'experience_score': max_score}

                elif years_of_experience>=score.get('min') and years_of_experience <score.get('max'):
                    return {'experience_score': score.get('score')/100 * max_score}

        else:
            return {'experience_score':0}

    def get_doctors_score(self, doctor_in_hosp_count,doctor):
        max_score = self.max_score_dict.get('doctors_in_clinic_score')
        if max_score:
            maximum = max(doctor_in_hosp_count, key=doctor_in_hosp_count.get)
            doctors_count = int(doctor_in_hosp_count[maximum])

            # for hospital in doctor.hospitals.all():
            #     if hospital.id and doctor_in_hosp_count.get(hospital.id):
            #         if doctor_in_hosp_count[hospital.id] > doctors_count:
            #             doctors_count = doctor_in_hosp_count[hospital.id]

            doctors_score_list = self.scoring_data.get('doctors_in_clinic')
            for score in doctors_score_list:
                if doctors_count >=100:
                    return {'doctors_in_clinic_score': max_score}

                elif doctors_count >= score.get('min') and doctors_count < score.get('max'):
                    return {'doctors_in_clinic_score': score.get('score')/100 * max_score}
        return {'doctors_in_clinic_score': 0}

    def get_final_score(self, doctor, *args, **kwargs):
        if self:
            final_score = 0
            priority_score = 0
            final_score_list = self.scoring_data.get('weightage')[0]
            final_score = kwargs['years_of_experience_score'] * final_score_list['years_of_experience'] + \
                          kwargs['doctors_in_clinic_score'] * final_score_list['doctors_in_clinic'] +\
                          kwargs['avg_ratings_score'] * final_score_list['average_ratings'] + \
                          kwargs['ratings_count_score'] * final_score_list['ratings_count'] + \
                            kwargs['discount'] * final_score_list['discount'] + kwargs['partner_app_activity_score'] * final_score_list['partner_app_activity']

            if doctor.priority_score:
                priority_score += doctor.priority_score
            if doctor.hospitals.all() and priority_score == 0:
                for hosp in doctor.hospitals.all():
                    if hosp.priority_score > priority_score:
                        priority_score = hosp.priority_score

            if priority_score == 0:
                network_hospitals = doctor.hospitals.all().filter(network__isnull=False)
                if network_hospitals:
                    for data in network_hospitals:
                        if data.network and data.network.priority_score > priority_score:
                            priority_score = data.network.priority_score

            final_score += priority_score

            return {'final_score': final_score}

    def delete_search_score(self):
        RawSql('''delete from search_score''', []).execute()
        return "success"
    
    def create_doctor_score(self):
        RawSql('''update doctor d set search_score=(select final_score from search_score ss where ss.doctor_id=d.id)''', []).execute()
        return "success"
    
    #@task(bind=True)
    #@transaction.atomic
    def create_search_score(self):
        print(self.delete_search_score())
        print(self.calculate())
        print(self.create_doctor_score())