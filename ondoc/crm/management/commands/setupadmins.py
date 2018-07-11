from django.core.management.base import BaseCommand
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from django.db import transaction


class Command(BaseCommand):

    help = 'Create default Appointment Admins'

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=int, nargs='?', default=0)

    @transaction.atomic
    def handle(self, *args, **options):
        user_id = options['user_id']
        if user_id == 0:
            doctors = doc_models.Doctor.objects.select_related('user').all()
        else:
            doctors = []
            admin_query = auth_models.GenericAdmin.objects.select_related('doctor').\
                filter(user_id=user_id, permission_type=auth_models.GenericAdmin.APPOINTMENT).distinct('doctor')
            if admin_query:
                for admin in admin_query.all():
                    if admin.doctor:
                        doctors.append(admin.doctor)
                    else:
                        if admin.hospital:
                            if admin.hospital.is_appointment_manager:
                                auth_models.GenericAdmin.objects.filter(hospital=admin.hospital,
                                                                        permission_type=auth_models.GenericAdmin.APPOINTMENT,
                                                                        doctor__isnull=False).update(is_disabled=True)

        if doctors:
            for doc in doctors:
                auth_models.GenericAdmin.create_admin_permissions(doc)
                auth_models.GenericAdmin.create_admin_billing_permissions(doc)
            self.stdout.write('Successfully Created Admin Permissions')
        else:
            self.stdout.write('No Permissions Found')

