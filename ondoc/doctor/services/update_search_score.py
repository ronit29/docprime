from ondoc.doctor import models as doctor_models
from django.db.models import Count
from ondoc.api.v1.utils import RawSql
import datetime


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
                                 "weightage": [{"popularity_score": 0.50,
                                                "years_of_experience": 0.25,
                                                "doctors_in_clinic": 0.25}]

                             }

        doc_popularity = RawSql("select reference_id id, popularity_score score from source_identifier si inner join doctor_popularity dp on dp.unique_identifier= si.unique_identifier where type = 1 ", []).fetch_all()
        self.popularity_data = dict()
        for dp in doc_popularity:
            self.popularity_data[dp['id']] = dp['score']

    def calculate(self):
        hosp_dict = doctor_models.Hospital.objects.prefetch_related('assoc_doctors').annotate(doctors_count=Count('assoc_doctors__id')).values('id','doctors_count')
        doctor_in_hosp_count = dict()
        for hosp in hosp_dict:
            doctor_in_hosp_count[hosp['id']] = hosp['doctors_count']

        doctors = doctor_models.Doctor.objects.all().order_by('id')
        final_result = dict()
        score_obj_list = []

        for doctor in doctors:
            result = list()
            final_result[doctor.id] = result
            result.append(self.get_popularity_score(doctor))
            result.append(self.get_practice_score(doctor))
            result.append(self.get_doctors_score(doctor_in_hosp_count,doctor))
            result.append(self.get_final_score(result))

            score_obj_list.append(doctor_models.SearchScore(doctor=doctor, popularity_score=result[0]['popularity_score'],
                                                            years_of_experience_score=result[1]['experience_score'],
                                                            doctors_in_clinic_score=result[2]['doctors_in_clinic_score'],
                                                            final_score=result[3]['final_score']))
        bulk_created = doctor_models.SearchScore.objects.bulk_create(score_obj_list)
        if bulk_created:
            return 'success'
        else:
            return 'failure'

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

    def get_final_score(self, result):
        if result:
            final_score = 0
            final_score_list = self.scoring_data.get('weightage')[0]
            final_score = result[0]['popularity_score'] * final_score_list['popularity_score'] + result[1]['experience_score'] * final_score_list['years_of_experience'] +  result[2]['doctors_in_clinic_score'] * final_score_list['doctors_in_clinic']
            return {'final_score': final_score}










