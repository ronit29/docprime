from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from ondoc.banner.models import Banner, SliderLocation, BannerLocation, EmailBanner, RecommenderThrough, Recommender
from ondoc.common.models import PaymentOptions, UserConfig, Feature, Service, Remark, MatrixMappedCity, \
    MatrixMappedState, GenericNotes, BlacklistUser, BlockedStates
from ondoc.corporate_booking.models import CorporateDeal, Corporates, CorporateDocument
from ondoc.coupon.models import Coupon, UserSpecificCoupon, RandomGeneratedCoupon
from ondoc.crm.constants import constants
from ondoc.doctor.models import (Doctor, Hospital, DoctorClinicTiming, DoctorClinic,
                                 DoctorQualification, Qualification, Specialization, DoctorLanguage,
                                 DoctorAward, DoctorAssociation, DoctorExperience, DoctorMedicalService,
                                 DoctorImage, DoctorDocument, Language, MedicalService, HospitalNetwork,
                                 DoctorMobile, DoctorEmail, HospitalSpeciality, HospitalAward,
                                 HospitalAccreditation, HospitalImage, HospitalDocument,
                                 HospitalCertification, College, HospitalNetworkManager,
                                 HospitalNetworkHelpline, HospitalNetworkEmail,
                                 HospitalNetworkAccreditation, HospitalNetworkAward, HospitalNetworkDocument,
                                 HospitalNetworkCertification, DoctorPracticeSpecialization, AboutDoctor,
                                 DoctorMapping, OpdAppointment, CommonMedicalCondition, CommonSpecialization,
                                 MedicalCondition, PracticeSpecialization, SpecializationDepartment,
                                 SpecializationField, DoctorLeave,
                                 MedicalConditionSpecialization, CompetitorInfo, CompetitorMonthlyVisit,
                                 SpecializationDepartmentMapping, CancellationReason, UploadDoctorData,
                                 HospitalServiceMapping, HealthInsuranceProviderHospitalMapping,
                                 HealthInsuranceProvider, HospitalHelpline, HospitalTiming, CommonHospital)

from ondoc.diagnostic.models import (Lab, LabTiming, LabImage, GenericLabAdmin,
                                     LabManager, LabAccreditation, LabAward, LabCertification,
                                     LabNetwork, LabNetworkCertification,
                                     LabNetworkAward, LabNetworkAccreditation, LabNetworkEmail,
                                     LabNetworkHelpline, LabNetworkManager, LabTest,
                                     LabTestType, LabService, LabAppointment, LabDoctorAvailability,
                                     LabDoctor, LabDocument, LabPricingGroup, LabNetworkDocument, CommonTest,
                                     CommonDiagnosticCondition, DiagnosticConditionLabTest, HomePickupCharges,
                                     TestParameter, ParameterLabTest, LabTestPackage, LabReportFile, LabReport,
                                     CommonPackage, LabTestCategory, LabTestCategoryMapping,
                                     LabTestRecommendedCategoryMapping, QuestionAnswer, FrequentlyAddedTogetherTests,
                                     LabTestGroup, LabTestGroupMapping, LabTestGroupTiming)

from ondoc.insurance.models import (Insurer, InsurancePlans, InsuranceThreshold, InsuranceCity, StateGSTCode,
                                    InsuranceDistrict, InsuranceTransaction, InsuranceDeal, InsuranceDisease,
                                    UserInsurance, InsurancePlanContent, InsuredMembers, InsurerAccount, InsuranceLead,
                                    InsuranceDiseaseResponse, InsurerPolicyNumber, InsuranceCancelMaster,
                                    EndorsementRequest, InsuredMemberDocument, InsuredMemberHistory, ThirdPartyAdministrator,
                                    UserBank, UserBankDocument, InsurerAccountTransfer)

from ondoc.procedure.models import Procedure, ProcedureCategory, CommonProcedureCategory, DoctorClinicProcedure, \
    ProcedureCategoryMapping, ProcedureToCategoryMapping, CommonProcedure, IpdProcedure, IpdProcedureFeatureMapping, \
    DoctorClinicIpdProcedure, IpdProcedureCategoryMapping, IpdProcedureCategory, CommonIpdProcedure, \
    IpdProcedureDetailType, IpdProcedureDetail, IpdProcedureSynonym, IpdProcedureSynonymMapping, \
    IpdProcedurePracticeSpecialization, IpdProcedureLead, Offer, IpdCostEstimateRoomType, IpdProcedureCostEstimate, \
    IpdCostEstimateRoomTypeMapping, IpdProcedureLeadCostEstimateMapping, UploadCostEstimateData
from ondoc.reports import models as report_models

from ondoc.diagnostic.models import LabPricing
from ondoc.integrations.models import IntegratorMapping, IntegratorProfileMapping, IntegratorReport, IntegratorTestMapping, IntegratorTestParameterMapping
from ondoc.subscription_plan.models import Plan, PlanFeature, PlanFeatureMapping, UserPlanMapping

from ondoc.web.models import Career, OnlineLead, UploadImage
from ondoc.ratings_review import models as rating_models
from ondoc.articles.models import Article, ArticleLinkedUrl, LinkedArticle, ArticleContentBox, ArticleCategory

from ondoc.authentication.models import BillingAccount, SPOCDetails, GenericAdmin, User, Merchant, AssociatedMerchant, DoctorNumber
from ondoc.account.models import MerchantPayout
from ondoc.seo.models import Sitemap, NewDynamic
from ondoc.elastic.models import DemoElastic
from ondoc.location.models import EntityUrls, CompareLabPackagesSeoUrls, CompareSEOUrls, CityLatLong

#from fluent_comments.admin import CommentModel
from threadedcomments.models import ThreadedComment
from fluent_comments.models import FluentComment
from django_comments.models import Comment

class Command(BaseCommand):
    help = 'Create groups and setup permissions for teams'


    def handle(self, *args, **options):

        # setup permissions for field_agents
        group, created = Group.objects.get_or_create(name=constants['DOCTOR_NETWORK_GROUP_NAME'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Merchant, Doctor, Hospital, HospitalNetwork, UploadDoctorData, Remark, Qualification, College, Specialization, GenericAdmin)
        for cl, ct in content_types.items():

            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        #needed for a wierd django error
        content_types = ContentType.objects.get_for_model(DoctorClinicProcedure)
        content_types = ContentType.objects.get_for_model(Procedure)


        content_types = ContentType.objects.get_for_models(
            DoctorClinic, DoctorClinicTiming,
            DoctorQualification, DoctorLanguage, DoctorAward, DoctorAssociation,
            DoctorExperience, DoctorMedicalService, DoctorImage, DoctorDocument,
            DoctorMobile, DoctorEmail, HospitalSpeciality,
            HospitalAward, HospitalAccreditation, HospitalImage, HospitalDocument,
            HospitalCertification, HospitalNetworkManager, HospitalNetworkHelpline,
            HospitalNetworkEmail, HospitalNetworkAccreditation, HospitalNetworkAward,
            HospitalNetworkCertification, DoctorPracticeSpecialization, CompetitorInfo, CompetitorMonthlyVisit,
            SPOCDetails, DoctorClinicProcedure, AssociatedMerchant)

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
                                                           LabDoctor, LabDocument, HomePickupCharges)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(MatrixMappedCity, MatrixMappedState)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

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

        content_types = ContentType.objects.get_for_models(Merchant, Doctor, Hospital, HospitalNetwork,
                                                           Qualification, Specialization, Language, MedicalService,
                                                           College, SpecializationDepartment,
                                                           SpecializationField,
                                                           SpecializationDepartmentMapping, UploadDoctorData, Remark
                                                           )

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(LabTest, LabTestType, LabService, TestParameter, LabTestGroup,
                                                           LabTestGroupMapping, LabTestGroupTiming)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(ParameterLabTest, LabTestPackage)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model)
                )
            group.permissions.add(*permissions)


        content_types = ContentType.objects.get_for_models(
            DoctorClinic, DoctorClinicTiming, GenericAdmin, GenericLabAdmin,
            DoctorQualification, DoctorLanguage, DoctorAward, DoctorAssociation,
            DoctorExperience, DoctorMedicalService, DoctorImage, DoctorDocument,
            DoctorMobile, DoctorEmail, HospitalSpeciality, DoctorNumber,
            HospitalAward, HospitalAccreditation, HospitalImage, HospitalDocument,
            HospitalCertification, HospitalNetworkManager, HospitalNetworkHelpline,
            HospitalNetworkEmail, HospitalNetworkAccreditation, HospitalNetworkAward,
            HospitalNetworkCertification, DoctorPracticeSpecialization, HospitalNetworkDocument, CompetitorInfo,
            CompetitorMonthlyVisit, SPOCDetails, DoctorClinicProcedure, AssociatedMerchant)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(LabTiming, LabImage,
        LabManager,LabAccreditation, LabAward, LabCertification,
        LabNetworkCertification, LabNetworkAward, HomePickupCharges,
        LabNetworkAccreditation, LabNetworkEmail, LabNetworkHelpline,
        LabNetworkManager,LabService,LabDoctorAvailability,LabDoctor, LabDocument, LabNetworkDocument)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(MatrixMappedCity, MatrixMappedState)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        # setup permissions for super qc team
        group, created = Group.objects.get_or_create(name=constants['SUPER_QC_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Doctor, Hospital, HospitalNetwork, Lab, LabNetwork)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct), Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(Doctor, Hospital)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct), Q(codename='delete_' + ct.model))
            group.permissions.add(*permissions)


        content_types = ContentType.objects.get_for_models(
            Qualification, Specialization, Language, MedicalService, College, LabTest,
            LabTestType, LabService, TestParameter, PracticeSpecialization,
            SpecializationField, SpecializationDepartment, SpecializationDepartmentMapping,
            Procedure, ProcedureCategory, CommonProcedureCategory,
            ProcedureToCategoryMapping, ProcedureCategoryMapping, LabTestCategory, Merchant, CancellationReason, UploadDoctorData,
            LabTestGroup, LabTestGroupMapping, LabTestGroupTiming
        )

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)


        content_types = ContentType.objects.get_for_models(ParameterLabTest, LabTestPackage, LabTestCategoryMapping)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model)
                )
            group.permissions.add(*permissions)



        content_types = ContentType.objects.get_for_models(
            DoctorClinic, DoctorClinicTiming,
            DoctorQualification, DoctorLanguage, DoctorAward, DoctorAssociation,
            DoctorExperience, DoctorMedicalService, DoctorImage, DoctorDocument,
            DoctorMobile, DoctorEmail, HospitalSpeciality, DoctorNumber,
            HospitalAward, HospitalAccreditation, HospitalImage, HospitalDocument,
            HospitalCertification, HospitalNetworkManager, HospitalNetworkHelpline,
            HospitalNetworkEmail, HospitalNetworkAccreditation, HospitalNetworkAward,
            HospitalNetworkCertification, DoctorPracticeSpecialization, HospitalNetworkDocument, CompetitorInfo,
            CompetitorMonthlyVisit, SPOCDetails, GenericAdmin, GenericLabAdmin, DoctorClinicProcedure, AssociatedMerchant, MatrixMappedState, MatrixMappedCity)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(LabTiming, LabImage,
                                                           LabManager, LabAccreditation, LabAward, LabCertification,
                                                           LabNetworkCertification, LabNetworkAward,
                                                           LabNetworkAccreditation, LabNetworkEmail,
                                                           LabNetworkHelpline, HomePickupCharges, 
                                                           LabNetworkManager, LabService, LabDoctorAvailability,
                                                           LabDoctor, LabDocument, LabNetworkDocument)

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

        content_types = ContentType.objects.get_for_models(LabPricingGroup)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

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


        # Create coupon group
        group, created = Group.objects.get_or_create(name=constants['COUPON_MANAGEMENT_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Coupon, UserSpecificCoupon)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(RandomGeneratedCoupon)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)


        content_types = ContentType.objects.get_for_models(Banner, BannerLocation, SliderLocation)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        # content_types = ContentType.objects.get_for_models(LabTest)
        #
        # for cl, ct in content_types.items():
        #     permissions = Permission.objects.filter(
        #         Q(content_type=ct),
        #         Q(codename='change_' + ct.model))
        #
        #     group.permissions.add(*permissions)

        # Create about doctor group
        self.create_about_doctor_group()

        # Create doctor image cropping team
        self.create_cropping_group()

        #Create testing group
        self.create_testing_group()

        # Create OPD appointment management team
        self.create_opd_appointment_management_group()

        # Create Lab appointment management team
        self.create_lab_appointment_management_group()

        # Create Chat Conditions Team group
        self.create_conditions_management_group()

        #Create report team
        self.create_report_team()

        self.create_elastic_group()

        self.create_labtest_team()

        self.create_merchant_team()

        #Create insurance group
        self.create_insurance_group()

        #creating super insurance group
        self.create_super_insurance_group()

        #creating corporate_group
        self.create_corporate_group()

        # creating group for blocked state and blacklist users.
        self.create_blocked_state_group()

        #Create XL Data Export Group
        Group.objects.get_or_create(name=constants['DATA_EXPORT_GROUP'])

        # Create Article team Group
        group, created = Group.objects.get_or_create(name=constants['ARTICLE_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Article, Sitemap, ArticleContentBox, ArticleCategory, EntityUrls)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(ArticleLinkedUrl, LinkedArticle, NewDynamic)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(Hospital)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        #Review team Group
        group, created = Group.objects.get_or_create(name=constants['REVIEW_TEAM_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(rating_models.RatingsReview, rating_models.ReviewCompliments)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        # DoctorAvailibility team Group
        group, created = Group.objects.get_or_create(name=constants['DOC_AVAILABILITY_TEAM_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(DoctorLeave)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model)|
                Q(codename='delete_' + ct.model)
            )
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

        group, created = Group.objects.get_or_create(name=constants['DOCTOR_SALES_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(DoctorEmail, DoctorMobile, DoctorClinic, DoctorClinicTiming, DoctorClinicProcedure)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(Doctor, DoctorClinic, DoctorPracticeSpecialization,
                                                           DoctorQualification, DoctorLanguage, DoctorClinicProcedure)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        group, created = Group.objects.get_or_create(name=constants['PRODUCT_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(LabTestRecommendedCategoryMapping, Banner, SliderLocation, UserConfig,
                                                           CompareSEOUrls, CompareLabPackagesSeoUrls,
                                                           NewDynamic, QuestionAnswer, FrequentlyAddedTogetherTests,
                                                           IpdProcedureFeatureMapping, HospitalServiceMapping,
                                                           DoctorClinic, DoctorClinicIpdProcedure,
                                                           HealthInsuranceProviderHospitalMapping, IpdProcedureCategoryMapping, CommonIpdProcedure,
                                                           HospitalHelpline, IpdProcedure, HospitalTiming,
                                                           IpdProcedureDetailType, IpdProcedureDetail, IpdProcedureSynonym, IpdProcedureSynonymMapping,
                                                           EmailBanner, RecommenderThrough, Recommender,
                                                           IpdProcedurePracticeSpecialization, CityLatLong, CommonHospital)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(PaymentOptions, EntityUrls, Feature, Service, Doctor,
                                                           HealthInsuranceProvider, IpdProcedureCategory, Plan,
                                                           PlanFeature, PlanFeatureMapping, UserPlanMapping, UploadImage,
                                                           Offer)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(Coupon, UserSpecificCoupon, Hospital, HospitalNetwork)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        # Create integration group
        group, created = Group.objects.get_or_create(name=constants['INTEGRATION_MANAGEMENT_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(IntegratorMapping, IntegratorProfileMapping, LabTest, LabNetwork,
                                                           IntegratorReport, IntegratorTestMapping, IntegratorTestParameterMapping)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)


        group, created = Group.objects.get_or_create(name=constants['WELCOME_CALLING_TEAM'])
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

        content_types = ContentType.objects.get_for_models(Merchant,
                                                           Qualification, Specialization, Language, MedicalService,
                                                           College, SpecializationDepartment,
                                                           SpecializationField,
                                                           SpecializationDepartmentMapping, UploadDoctorData, Remark
                                                           )

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(LabTest, LabTestType, LabService, TestParameter)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(ParameterLabTest, LabTestPackage)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model)
            )
            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(
            DoctorClinic, DoctorClinicTiming, GenericAdmin, GenericLabAdmin,
            DoctorQualification, DoctorLanguage, DoctorAward, DoctorAssociation,
            DoctorExperience, DoctorMedicalService, DoctorImage, DoctorDocument,
            DoctorMobile, DoctorEmail, HospitalSpeciality, DoctorNumber,
            HospitalAward, HospitalAccreditation, HospitalImage, HospitalDocument,
            HospitalCertification, HospitalNetworkManager, HospitalNetworkHelpline,
            HospitalNetworkEmail, HospitalNetworkAccreditation, HospitalNetworkAward,
            HospitalNetworkCertification, DoctorPracticeSpecialization, HospitalNetworkDocument, CompetitorInfo,
            CompetitorMonthlyVisit, SPOCDetails, DoctorClinicProcedure, AssociatedMerchant)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(LabTiming, LabImage,
                                                           LabManager, LabAccreditation, LabAward, LabCertification,
                                                           LabNetworkCertification, LabNetworkAward, HomePickupCharges,
                                                           LabNetworkAccreditation, LabNetworkEmail, LabNetworkHelpline,
                                                           LabNetworkManager, LabService, LabDoctorAvailability,
                                                           LabDoctor, LabDocument, LabNetworkDocument)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(MatrixMappedCity, MatrixMappedState)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        group, created = Group.objects.get_or_create(name=constants['APPOINTMENT_REFUND_TEAM'])
        # group.permissions.clear()

        group, created = Group.objects.get_or_create(name=constants['IPD_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Doctor, Hospital, IpdProcedure, HealthInsuranceProvider,
                                                           ThirdPartyAdministrator, IpdProcedureLead, UserInsurance)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct), Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        group, created = Group.objects.get_or_create(name=constants['APPOINTMENT_OTP_BYPASS_AGENT_TEAM'])
        # group.permissions.clear()

        content_types = ContentType.objects.get_for_models(IpdCostEstimateRoomType, IpdProcedureCostEstimate,
                                                           IpdCostEstimateRoomTypeMapping, IpdProcedureLeadCostEstimateMapping,
                                                           UploadCostEstimateData)
        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)

        self.stdout.write('Successfully created groups and permissions')

        self.setup_comment_group()
        self.create_common_groups()

    def create_about_doctor_group(self):
        group, created = Group.objects.get_or_create(name=constants['ABOUT_DOCTOR_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(AboutDoctor, DoctorPracticeSpecialization, DoctorQualification,
                                                           DoctorClinicTiming, DoctorClinic, DoctorLanguage,
                                                           DoctorAward, DoctorAssociation, DoctorExperience, DoctorClinicProcedure,
                                                           for_concrete_models=False)

        for cl, ct in content_types.items():
            permissions = Permission.objects.get_or_create(
                content_type=ct, codename='change_' + ct.model)

            permissions = Permission.objects.filter(
                content_type=ct, codename='change_' + ct.model)
            group.permissions.add(*permissions)

    def create_cropping_group(self):
        # Create Cropping team Group
        group, created = Group.objects.get_or_create(name=constants['DOCTOR_IMAGE_CROPPING_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(DoctorImage)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

    def create_testing_group(self):
        group, created = Group.objects.get_or_create(name=constants['TEST_USER_GROUP'])

    def create_opd_appointment_management_group(self):
        # Create appointment management team
        group, created = Group.objects.get_or_create(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(OpdAppointment)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

    def create_lab_appointment_management_group(self):
        # Create appointment management team
        group, created = Group.objects.get_or_create(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(LabAppointment)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)


        content_types = ContentType.objects.get_for_models(LabReportFile, LabReport)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))


            group.permissions.add(*permissions)


    def create_conditions_management_group(self):
        # Create chat conditions team
        group, created = Group.objects.get_or_create(name=constants['CONDITIONS_MANAGEMENT_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(CommonMedicalCondition, CommonSpecialization,
                                                           MedicalConditionSpecialization,  MedicalCondition,
                                                           CommonTest, CommonDiagnosticCondition,
                                                           DiagnosticConditionLabTest, CommonPackage, CommonProcedureCategory,
                                                           CommonProcedure)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

    def create_report_team(self):
        group, created = Group.objects.get_or_create(name=constants['REPORT_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(report_models.GeneratedReport, for_concrete_models=False)

        for cl, ct in content_types.items():
            Permission.objects.get_or_create(content_type=ct, codename='change_' + ct.model)
            permissions = Permission.objects.filter(content_type=ct, codename='change_' + ct.model)
            group.permissions.add(*permissions)


    def create_labtest_team(self):
        group, created = Group.objects.get_or_create(name=constants['LAB_TEST_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(LabTest, TestParameter, ParameterLabTest)

        for cl, ct in content_types.items():
            Permission.objects.get_or_create(content_type=ct, codename='change_' + ct.model)
            permissions = Permission.objects.filter(content_type=ct, codename='change_' + ct.model)
            group.permissions.add(*permissions)

    def create_merchant_team(self):
        group, created = Group.objects.get_or_create(name=constants['MERCHANT_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Merchant)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(AssociatedMerchant)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(MerchantPayout, UserInsurance)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)


    def create_elastic_group(self):

        group, created = Group.objects.get_or_create(name=constants['ELASTIC_TEAM'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(DemoElastic)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model) |
                Q(codename='delete_' + ct.model))

            group.permissions.add(*permissions)

    def setup_comment_group(self):
        group, created = Group.objects.get_or_create(name=constants['COMMENT_TEAM'])
        group.permissions.clear()

        # content_types = ContentType.objects.get_for_models(Comment)
        # print(content_types)
        #
        # for cl, ct in content_types.items():
        #     permissions = Permission.objects.filter(
        #         Q(content_type=ct),
        #         Q(codename='add_' + ct.model) | Q(codename='change_' + ct.model))
        #
        #     group.permissions.add(*permissions)


        content_types = ContentType.objects.get_for_models(FluentComment, for_concrete_models=False)
        # print(content_types)

        for cl, ct in content_types.items():
            permissions = Permission.objects.get_or_create(
                content_type=ct, codename='change_' + ct.model)
            permissions = Permission.objects.get_or_create(
                content_type=ct, codename='add_' + ct.model)


            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) | Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

    def create_common_groups(self):
        group, created = Group.objects.get_or_create(name=constants['APPOINTMENT_OTP_TEAM'])

    def create_insurance_group(self):
        group, created = Group.objects.get_or_create(name=constants['INSURANCE_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Insurer, InsuranceDisease, InsurerAccount,
                                                           InsurancePlanContent, InsurancePlans, InsuranceCity,
                                                           StateGSTCode, InsuranceDistrict, InsuranceThreshold,
                                                           UserInsurance, InsuranceDeal, InsuranceLead,
                                                           InsuranceTransaction, InsuranceDiseaseResponse,
                                                           InsuredMembers, InsurerPolicyNumber, InsuranceCancelMaster,
                                                           EndorsementRequest, InsuredMemberDocument,
                                                           InsuredMemberHistory, UserBank, UserBankDocument,
                                                           GenericNotes)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)

        content_types = ContentType.objects.get_for_models(UserInsurance)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model))

            group.permissions.add(*permissions)

    def create_super_insurance_group(self):
        group, created = Group.objects.get_or_create(name=constants['SUPER_INSURANCE_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Insurer, InsuranceDisease, InsurerAccount,
                                                           InsurancePlanContent, InsurancePlans, InsuranceCity,
                                                           StateGSTCode, InsuranceDistrict, InsuranceThreshold,
                                                           UserInsurance, InsuranceDeal, InsuranceLead,
                                                           InsuranceTransaction, InsuranceDiseaseResponse,
                                                           InsuredMembers, InsurerPolicyNumber, InsuranceCancelMaster,
                                                           EndorsementRequest, InsuredMemberDocument,
                                                           InsuredMemberHistory, UserBank, UserBankDocument,
                                                           GenericNotes, InsurerAccountTransfer)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)


    def create_corporate_group(self):
        group, created = Group.objects.get_or_create(name=constants['CORPORATE_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(Corporates, CorporateDeal, Coupon, CorporateDocument,
                                                           MatrixMappedCity, MatrixMappedState)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))
            group.permissions.add(*permissions)


    def create_blocked_state_group(self):

        group, created = Group.objects.get_or_create(name=constants['BLOCK_STATE_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(BlacklistUser, BlockedStates)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)


        group, created = Group.objects.get_or_create(name=constants['BLOCK_USER_GROUP'])
        group.permissions.clear()

        content_types = ContentType.objects.get_for_models(BlacklistUser)

        for cl, ct in content_types.items():
            permissions = Permission.objects.filter(
                Q(content_type=ct),
                Q(codename='add_' + ct.model) |
                Q(codename='change_' + ct.model))

            group.permissions.add(*permissions)
