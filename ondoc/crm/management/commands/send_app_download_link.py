from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from ondoc.doctor.models import Doctor, DoctorMobile, DoctorEmail
from ondoc.notification.models import EmailNotification, SmsNotification


class Command(BaseCommand):
    help = 'Send App Download Link'
    delhi_mid_point = Point(77.216721, 28.644800, srid=4326)
    max_distance = 50000  # In Meters

    def handle(self, *args, **options):
        doctors = Doctor.objects.filter(hospitals__is_live=True,
                                        hospitals__location__distance_lte=(self.delhi_mid_point, self.max_distance)
                                        ).filter(onboarding_status=Doctor.ONBOARDED,
                                                 data_status=Doctor.QC_APPROVED,
                                                 user__isnull=True
                                                 ).distinct().values_list('id', flat=True)
        # test the above query
        # for d in Doctor.objects.filter(pk__in=doctors).annotate(distance=Distance('hospitals__location',
        #                                                                           self.delhi_mid_point)
        #                                                         ).values_list('distance', flat=True):
        #     if float(d.m) <= 50000:
        #         print(int(d.m)/1000)
        #     else:
        #         print("wrong query")
        for doctor_email in DoctorEmail.objects.filter(doctor__in=doctors, is_primary=True):
            EmailNotification.send_app_download_link(email=doctor_email.email, context={})

        for doctor_phone_number in DoctorMobile.objects.filter(doctor__in=doctors, is_primary=True):
            SmsNotification.send_app_download_link(phone_number=str(doctor_phone_number.number), context={})
