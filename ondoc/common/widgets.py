from ondoc.articles.models import MedicineSpecialization
from ondoc.doctor.models import PracticeSpecialization
import random


class ArticleFooterWidget():

    def __init__(self, article_obj):
        self.article = article_obj
        super().__init__()

    @property
    def widget_picker(self):
        widgets = [
            self.doctor_appointment_widget,
            self.lab_test_widget,
            self.health_package_widget
        ]
        resp = random.choice(widgets)
        return resp

    @property
    def doctor_appointment_widget(self):
        top_specializations = {
            "Obstetrician & Gynecologist": 363,
            "Dermatologist": 291,
            "Orthopedist": 414,
            "Dentist": 279,
            "General Physician": 329
        }

        resp = dict()
        article = self.article
        specializations_to_show = 5
        title = 'Book top doctors'
        discount = '50% off'
        article_specializations = {}

        if article:
            medicine_specializations = MedicineSpecialization.objects.filter(medicine=article)

        if medicine_specializations:
            ms_specialization_ids = list(map(lambda x: x.specialization_id, medicine_specializations))
            specializations = PracticeSpecialization.objects.filter(id__in=ms_specialization_ids)
            as_count = len(specializations)
            if as_count < specializations_to_show:

                for specialization in specializations:
                    article_specializations[specialization.name] = specialization.id

                for ts_key in top_specializations.keys():
                    article_specializations[ts_key] = top_specializations[ts_key]

                    if len(article_specializations) >= specializations_to_show:
                        break
            else:
                for specialization in specializations:
                    article_specializations[specialization.name] = specialization.id
        else:
            article_specializations = top_specializations

        resp["widget_type"] = 'DoctorAppointment'
        resp["title"] = title
        resp["discount"] = discount
        resp["specializations"] = article_specializations
        return resp

    @property
    def lab_test_widget(self):
        resp = dict()
        top_tests = {
            "Ultrasound whole abdomen": 11554,
            "CBC Hemogram": 9333,
            "Lipid Profile": 10809,
            "Thyroid Profile": 11359,
            "Liver function test": 10815
        }
        title = "Book lab tests"
        discount = "50% off"
        resp["widget_type"] = 'LabTest'
        resp["title"] = title
        resp["discount"] = discount
        resp["test"] = top_tests
        return resp

    @property
    def health_package_widget(self):
        resp = dict()
        title_first = "Book fully body checkup starting"
        price = "Rs 499"
        title_last = "with 60 tests covering heart, liver, lipid, iron, thyroid etc."
        resp["widget_type"] = 'HealthPackage'
        resp["title_first"] = title_first
        resp["price"] = price
        resp["title_last"] = title_last
        return resp
