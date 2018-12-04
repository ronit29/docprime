from django.core.management.base import BaseCommand
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from django.db import transaction


class Command(BaseCommand):

    help = 'Split Appointment Admins'

    def pem_object(self, obj, type):
        return auth_models.GenericAdmin.create_permission_object(user=obj.user, doctor=obj.doctor,
                                                                 name=obj.name,
                                                                 phone_number=obj.phone_number,
                                                                 hospital=obj.hospital,
                                                                 permission_type=type,
                                                                 is_disabled=obj.is_disabled,
                                                                 super_user_permission=obj.super_user_permission,
                                                                 write_permission=obj.write_permission,
                                                                 created_by=obj.created_by,
                                                                 source_type=obj.source_type,
                                                                 entity_type=obj.entity_type,
                                                                 )


    @transaction.atomic
    def handle(self, *args, **options):
        admin_query = auth_models.GenericAdmin.objects.filter(permission_type=auth_models.GenericAdmin.ALL)
        if admin_query.exists():
            admin_list= []
            for admin in admin_query.all():
                admin_list.append(self.pem_object(admin, auth_models.GenericAdmin.APPOINTMENT))
                admin_list.append(self.pem_object(admin, auth_models.GenericAdmin.BILLINNG))

            auth_models.GenericAdmin.objects.bulk_create(admin_list)
            admin_query.delete()
            self.stdout.write('Successfully Created Admin Permissions')
        else:
            self.stdout.write('No Permissions Found')


