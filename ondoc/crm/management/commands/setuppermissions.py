from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from ondoc.crm.constants import constants
from ondoc.doctor.models import (Doctor, Hospital, DoctorHospital,
                                 DoctorQualification, Qualification,
                                 Specialization, DoctorLanguage,
                                 DoctorAward, DoctorAssociation,
                                 DoctorExperience, DoctorMedicalService,
                                 DoctorImage, DoctorDocument, Language, MedicalService)


class Command(BaseCommand):
    help = 'Create groups and setup permissions for teams'

    def handle(self, *args, **options):

        # setup permissions for field_agents
        group, created = Group.objects.get_or_create(name=constants['DOCTOR_NETWORK_GROUP_NAME'])
        group.permissions.clear()


        content_types = ContentType.objects.get_for_models(Doctor, Hospital)
        for cl, ct in content_types.items():

            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)



        content_types = ContentType.objects.get_for_models(DoctorHospital,
                                                           DoctorQualification,
                                                           DoctorLanguage,
                                                           DoctorAward,
                                                           DoctorAssociation,
                                                           DoctorExperience,
                                                           DoctorMedicalService,
                                                           DoctorImage,
                                                           DoctorDocument)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)


        # setup permissions for qc team
        group, created = Group.objects.get_or_create(name=constants['QC_GROUP_NAME'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Doctor, Hospital)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct), Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(Qualification,
                                                           Specialization,
                                                           Language,
                                                           MedicalService)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(DoctorHospital,
                                                           DoctorQualification,
                                                           DoctorLanguage,
                                                           DoctorAward,
                                                           DoctorAssociation,
                                                           DoctorExperience,
                                                           DoctorMedicalService,
                                                           DoctorImage,
                                                           DoctorDocument)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        self.stdout.write('Successfully created groups and permissions')
