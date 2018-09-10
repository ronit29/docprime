from django.core.management.base import BaseCommand

from ondoc.authentication.models import GenericLabAdmin, User
from ondoc.diagnostic.models import LabManager


class Command(BaseCommand):
    help = 'Set lab managers as lab admins if he she is not a admin already.'

    # lab or lab network

    def handle(self, *args, **options):
        lab_managers = LabManager.objects.filter(contact_type=LabManager.SPOC)
        for lab_manager in lab_managers:
            lab = lab_manager.lab
            network = lab.network
            if not GenericLabAdmin.objects.filter(lab=lab, permission_type=GenericLabAdmin.APPOINTMENT,
                                                  phone_number=lab_manager.number).exists():
                GenericLabAdmin.objects.create(
                    user=User.objects.filter(phone_number=lab_manager.number).first() if User.objects.filter(
                        phone_number=lab_manager.number).exists() else None,
                    phone_number=lab_manager.number,
                    lab_network=None,
                    lab=lab,
                    permission_type=GenericLabAdmin.APPOINTMENT,
                    is_disabled=bool(network.manageable_lab_network_admins.all().count() if network else False),
                    super_user_permission=True,
                    read_permission=True,
                    write_permission=True)
