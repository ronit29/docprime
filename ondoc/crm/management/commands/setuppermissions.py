from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from ondoc.crm.constants import constants
from ondoc.doctor.models import (Doctor, Hospital, DoctorClinicTiming, DoctorClinic,
    DoctorQualification, Qualification, Specialization, DoctorLanguage,
    DoctorAward, DoctorAssociation, DoctorExperience, DoctorMedicalService,
    DoctorImage, DoctorDocument, Language, MedicalService, HospitalNetwork,
    DoctorMobile, DoctorEmail, HospitalSpeciality, HospitalAward,
    HospitalAccreditation, HospitalImage, HospitalDocument,
    HospitalCertification, College, HospitalNetworkManager,
    HospitalNetworkHelpline, HospitalNetworkEmail,
    HospitalNetworkAccreditation, HospitalNetworkAward,
    HospitalNetworkCertification, DoctorSpecialization, GeneralSpecialization, AboutDoctor, DoctorMapping)

from ondoc.diagnostic.models import (Lab, LabTiming, LabImage,
    LabManager,LabAccreditation, LabAward, LabCertification,
    LabNetwork,LabNetworkCertification,
    LabNetworkAward, LabNetworkAccreditation, LabNetworkEmail,
    LabNetworkHelpline, LabNetworkManager, LabTest,
    LabTestType, LabService,
    LabDoctorAvailability,LabDoctor,LabDocument)

from ondoc.diagnostic.models import LabPricing

from ondoc.web.models import Career, OnlineLead

from ondoc.articles.models import Article

class Command(BaseCommand):
    help = 'Create groups and setup permissions for teams'


    def handle(self, *args, **options):

        # setup permissions for field_agents
        group, created = Group.objects.get_or_create(name=constants['DOCTOR_NETWORK_GROUP_NAME'])
        group.permissions.clear()


        content_types = ContentType.objects.get_for_models(Doctor, Hospital, HospitalNetwork)
        for cl, ct in content_types.items():

            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(
            DoctorClinic, DoctorClinicTiming,
            DoctorQualification, DoctorLanguage, DoctorAward, DoctorAssociation,
            DoctorExperience, DoctorMedicalService, DoctorImage, DoctorDocument,
            DoctorMobile, DoctorEmail, HospitalSpeciality,
            HospitalAward, HospitalAccreditation, HospitalImage, HospitalDocument,
            HospitalCertification, HospitalNetworkManager, HospitalNetworkHelpline,
            HospitalNetworkEmail, HospitalNetworkAccreditation, HospitalNetworkAward,
            HospitalNetworkCertification, DoctorSpecialization)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(Lab, LabNetwork)
        for cl, ct in content_types.items():

            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(LabTiming, LabImage,
                                                           LabManager, LabAccreditation, LabAward, LabCertification,
                                                           LabNetworkCertification, LabNetworkAward,
                                                           LabNetworkAccreditation, LabNetworkEmail, LabNetworkHelpline,
                                                           LabNetworkManager, LabService, LabDoctorAvailability,
                                                           LabDoctor, LabDocument)

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

        content_types = ContentType.objects.get_for_models(Doctor, Hospital, HospitalNetwork)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct), Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(Lab, LabNetwork)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct), Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(
            Qualification, Specialization, Language, MedicalService, College, GeneralSpecialization)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(LabTest,
                                                           LabTestType, LabService)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(
            DoctorClinic, DoctorClinicTiming,
            DoctorQualification, DoctorLanguage, DoctorAward, DoctorAssociation,
            DoctorExperience, DoctorMedicalService, DoctorImage, DoctorDocument,
            DoctorMobile, DoctorEmail, HospitalSpeciality,
            HospitalAward, HospitalAccreditation, HospitalImage, HospitalDocument,
            HospitalCertification, HospitalNetworkManager, HospitalNetworkHelpline,
            HospitalNetworkEmail, HospitalNetworkAccreditation, HospitalNetworkAward,
            HospitalNetworkCertification, DoctorSpecialization)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(LabTiming, LabImage,
        LabManager,LabAccreditation, LabAward, LabCertification,
        LabNetworkCertification, LabNetworkAward,
        LabNetworkAccreditation, LabNetworkEmail, LabNetworkHelpline,
        LabNetworkManager,LabService,LabDoctorAvailability,LabDoctor, LabDocument)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        # Create Pricing Groups
        group, created = Group.objects.get_or_create(name=constants['LAB_PRICING_GROUP_NAME'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(LabPricing, for_concrete_models = False)

        for cl, ct in content_types.items():
            permissions = Permission.objects.get_or_create(
                content_type=ct, codename='change_' + ct.model)

            permissions = Permission.objects.filter(
                content_type=ct, codename='change_' + ct.model)


            group.permissions.add(*permissions)


        # Create careers Groups
        group, created = Group.objects.get_or_create(name=constants['CAREERS_MANAGEMENT_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Career)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                content_type=ct, codename='change_' + ct.model)

            group.permissions.add(*permissions)


        # Create careers Groups
        group, created = Group.objects.get_or_create(name=constants['ONLINE_LEADS_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(OnlineLead)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                content_type=ct, codename='change_' + ct.model)

            group.permissions.add(*permissions)

        #Create about doctor group
        self.create_about_doctor_group()

        #Create Article team Group
        group, created = Group.objects.get_or_create(name=constants['ARTICLE_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Article)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        # Create Doctor Mapping team Group
        group, created = Group.objects.get_or_create(name=constants['DOCTOR_MAPPING_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(DoctorMapping)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        self.stdout.write('Successfully created groups and permissions')

    def create_about_doctor_group(self):
        group, created = Group.objects.get_or_create(name=constants['ABOUT_DOCTOR_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(AboutDoctor, DoctorSpecialization, DoctorQualification,
                                                           DoctorClinicTiming, DoctorClinic, DoctorLanguage,
                                                           DoctorAward, DoctorAssociation, DoctorExperience,
                                                           for_concrete_models=False)

        for cl, ct in content_types.items():
            permissions = Permission.objects.get_or_create(
                content_type=ct, codename='change_' + ct.model)

            permissions = Permission.objects.filter(
                content_type=ct, codename='change_' + ct.model)
            group.permissions.add(*permissions)
