from ondoc.api.v1.ratings.serializers import GoogleRatingsGraphSerializer
from ondoc.doctor import models as doctor_models
from django.db.models import Count, Case, When, F, Prefetch
from ondoc.api.v1.utils import RawSql
import datetime
from celery import task
from django.db import transaction


class DoctorSearchScore:
    def __init__(self):
        self.scoring_data = {"popularity_score": [{"min": 0, "max": 1, "score": 0},
                                                              {"min": 1, "max": 2, "score": 2},
                                                              {"min": 2, "max": 4, "score": 4},
                                                              {"min": 4, "max": 6, "score": 6},
                                                              {"min": 6, "max": 8, "score": 8},
                                                              {"min": 8, "max": 10, "score": 10}],

                                 "years_of_experience": [{"min": 0, "max": 5, "score": 0},
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
                                                "doctors_in_clinic": 0.40,
                                                "average_ratings": 0.10,
                                                "ratings_count": 0.10}],

                                 "average_ratings": [{"min": 0, "max": 3, "score": 0},
                                                        {"min": 3, "max": 3.5, "score": 3},
                                                        {"min": 3.5, "max": 4, "score": 7}],

                                 "ratings_count": [{"min": 0, "max": 5, "score": 0},
                                                        {"min": 5, "max": 10, "score": 3},
                                                        {"min": 10, "max": 15, "score": 7}]

                             }

        doc_popularity = RawSql("select reference_id id, popularity_score score from source_identifier si inner join doctor_popularity dp on dp.unique_identifier= si.unique_identifier where type = 1 ", []).fetch_all()
        self.popularity_data = dict()
        for dp in doc_popularity:
            self.popularity_data[dp['id']] = dp['score']

    def calculate(self):
        doctor_in_hosp_count = dict()
        hospitals_without_network = doctor_models.Hospital.objects.prefetch_related('assoc_doctors').filter(
            network__isnull=True).annotate(doctors_count=Count('assoc_doctors__id'))

        for hosp in hospitals_without_network:
            doctor_in_hosp_count[hosp.id] = hosp.doctors_count

        hospitals_with_network = doctor_models.Hospital.objects.select_related('network').filter(
            network__isnull=False).annotate(
            hosp_network_doctors_count=Count(Case(When(network__isnull=False, then=F('network__assoc_hospitals__assoc_doctors')))))

        for hosp in hospitals_with_network:
            doctor_in_hosp_count[hosp.id] = hosp.hosp_network_doctors_count

        doctors = doctor_models.Doctor.objects.all().prefetch_related("hospitals", "doctor_clinics", "doctor_clinics__hospital",
                                                "doctor_clinics__hospital__hospital_place_details").order_by('id')
        final_result = dict()
        score_obj_list = []

        for doctor in doctors:
            result = list()
            final_result[doctor.id] = result
            result.append(self.get_popularity_score(doctor))
            result.append(self.get_practice_score(doctor))
            result.append(self.get_doctors_score(doctor_in_hosp_count, doctor))
            result.append(self.get_doctor_ratings(doctor))
            result.append(self.get_doctor_ratings_count(doctor))
            result.append(self.get_final_score(result, doctor))

            score_obj_list.append(doctor_models.SearchScore(doctor=doctor, popularity_score=result[0]['popularity_score'],
                                                            years_of_experience_score=result[1]['experience_score'],
                                                            doctors_in_clinic_score=result[2]['doctors_in_clinic_score'],
                                                            avg_ratings_score=result[3]['avg_ratings_score'],
                                                            ratings_count_score=result[4]['ratings_count'],
                                                            final_score=result[5]['final_score']))
        bulk_created = doctor_models.SearchScore.objects.bulk_create(score_obj_list)
        if bulk_created:
            return 'success'
        else:
            return 'failure'

    def get_doctor_ratings(self, doctor):
        average_ratings = self.scoring_data.get('average_ratings')
        if doctor.avg_rating and doctor.avg_rating >= 1:
            for score in average_ratings:
                if doctor.avg_rating >= 4:
                    return {'avg_ratings_score': 10}

                elif doctor.avg_rating >= score.get('min') and doctor.avg_rating < score.get('max'):
                    return {'avg_ratings_score': score.get('score')}
        else:
            if doctor.hospitals.all():
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
                        return {'avg_ratings_score': 10}

                    elif google_rating >= score.get('min') and google_rating < score.get('max'):
                        return {'avg_ratings_score': score.get('score')}
            return {'avg_ratings_score': 0}

    def get_doctor_ratings_count(self, doctor):
        ratings_count = self.scoring_data.get('ratings_count')
        if doctor.rating_data and doctor.rating_data.get('rating_count'):
            for score in ratings_count:
                if doctor.rating_data.get('rating_count') >= 15:
                    return {'ratings_count': 10}

                elif doctor.rating_data.get('rating_count') >= score.get('min') and doctor.rating_data.get('rating_count') < score.get('max'):
                    return {'ratings_count': score.get('score')}

        return {'ratings_count': 0}

    def get_popularity_score(self, doctor):
        pop_score = self.popularity_data.get(doctor.id)
        if pop_score:
            popularity_list = self.scoring_data.get('popularity_score')            
            for score in popularity_list:
                if pop_score == 10:
                    return {'popularity_score': 10}

                elif pop_score >= score.get('min') and pop_score < score.get('max'):
                    return {'popularity_score': score.get('score')}
        else:
            return {'popularity_score': 0}

    def get_practice_score(self, doctor):
        score = 0
        if doctor.practicing_since:
            years_of_experience = datetime.datetime.now().year - doctor.practicing_since
            exp_years = self.scoring_data.get('years_of_experience')
            for score in exp_years:
                if years_of_experience>=25:
                    return {'experience_score': 10}

                elif years_of_experience>=score.get('min') and years_of_experience <score.get('max'):
                    return {'experience_score': score.get('score')}

        else:
            return {'experience_score':0}

    def get_doctors_score(self, doctor_in_hosp_count,doctor):
        doctors_count = 0
        for hospital in doctor.hospitals.all():
            if hospital.id and doctor_in_hosp_count.get(hospital.id):
                if doctor_in_hosp_count[hospital.id] > doctors_count:
                    doctors_count = doctor_in_hosp_count[hospital.id]

        doctors_score_list = self.scoring_data.get('doctors_in_clinic')
        for score in doctors_score_list:
            if doctors_count >=100:
                return {'doctors_in_clinic_score': 10}

            elif doctors_count >= score.get('min') and doctors_count < score.get('max'):
                return {'doctors_in_clinic_score': score.get('score')}

    def get_final_score(self, result, doctor):
        if result:
            final_score = 0
            priority_score = 0
            final_score_list = self.scoring_data.get('weightage')[0]
            final_score = result[0]['popularity_score'] * final_score_list['popularity_score'] + result[1][
                'experience_score'] * final_score_list['years_of_experience'] + result[2]['doctors_in_clinic_score'] * \
                          final_score_list['doctors_in_clinic'] + result[3]['avg_ratings_score'] * final_score_list[
                              'average_ratings'] + result[4]['ratings_count'] * final_score_list['ratings_count']
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



