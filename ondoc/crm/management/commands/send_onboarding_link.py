from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor, DoctorMobile, DoctorEmail
from ondoc.notification.models import EmailNotification, SmsNotification


class Command(BaseCommand):
    help = 'Send Onboarding Link'

    def handle(self, *args, **options):
        doctors = Doctor.objects.filter(hospitals__is_live=True).filter(
            onboarding_status=Doctor.ONBOARDED, data_status=Doctor.QC_APPROVED
        ).distinct().values_list('id', flat=True)

        for doctor_email in DoctorEmail.objects.filter(doctor__in=doctors, is_primary=True):
            EmailNotification.send_onboarding_link(email=doctor_email.email, context={})

        for doctor_phone_number in DoctorMobile.objects.filter(doctor__in=doctors, is_primary=True):
            SmsNotification.send_onboarding_link(phone_number=str(doctor_phone_number.number), context={})
