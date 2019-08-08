from ondoc.articles.models import MedicineSpecialization
from ondoc.doctor.models import PracticeSpecialization
import random
from django.conf import settings


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
        medicine_top_specializations = [int(i) for i in settings.MEDICINE_TOP_SPECIALIZATIONS]
        top_specializations = {
            "Obstetrician & Gynecologist": medicine_top_specializations[0],
            "Dermatologist": medicine_top_specializations[1],
            "Orthopedist": medicine_top_specializations[2],
            "Dentist": medicine_top_specializations[3],
            "General Physician": medicine_top_specializations[4]
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
                    if not top_specializations[ts_key] in ms_specialization_ids:
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
        medicine_top_tests = [int(i) for i in settings.MEDICINE_TOP_TESTS]
        top_tests = {
            "Ultrasound whole abdomen": medicine_top_tests[0],
            "CBC Hemogram": medicine_top_tests[1],
            "Lipid Profile": medicine_top_tests[2],
            "Thyroid Profile": medicine_top_tests[3],
            "Liver function test": medicine_top_tests[4]
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
        price = "Rs 549"
        title_last = "with 60 tests covering heart, liver, lipid, iron, thyroid etc."
        resp["widget_type"] = 'HealthPackage'
        resp["title_first"] = title_first
        resp["price"] = price
        resp["title_last"] = title_last
        return resp
