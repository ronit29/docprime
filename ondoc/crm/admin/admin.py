from django.contrib.gis import admin
from ondoc.common.models import PaymentOptions, UserConfig, Feature, Service, MatrixMappedState, MatrixMappedCity, \
    GlobalNonBookable, QRCode, BlacklistUser, BlockedStates, SponsorListingURL, \
    SponsorListingUtmTerm, SponsoredListingService, SponsorListingSpecialization, SearchCriteria, Certifications, GoogleLatLong
from ondoc.corporate_booking.models import Corporates, CorporateDeal, CorporateDocument
from ondoc.crm.admin.banner import BannerAdmin, SliderLocationAdmin, RecommenderAdmin, EmailBannerAdmin
from ondoc.crm.admin.location import ComparePackagesSEOUrlsAdmin
from ondoc.crm.admin.corporate_booking import CorporateDealAdmin, CorporatesAdmin
from ondoc.crm.admin.procedure import ProcedureCategoryAdmin, ProcedureAdmin, IpdProcedureAdmin, FeatureAdmin, \
    ServiceAdmin, HealthInsuranceProviderAdmin, IpdProcedureCategoryAdmin, IpdProcedureDetailAdmin, \
    IpdProcedureDetailTypeAdmin, IpdProcedureSynonymAdmin, IpdProcedureSynonymMappingAdmin, \
    IpdProcedurePracticeSpecializationAdmin, IpdProcedureLeadAdmin, OfferAdmin, \
    PotentialIpdLeadPracticeSpecializationAdmin, IpdProcedureCostEstimateAdmin, \
    IpdCostEstimateRoomTypeAdmin, UploadCostEstimateDataAdmin, PotentialIpdCityAdmin
from ondoc.crm.admin.subscription_plan import SubscriptionPlanAdmin, SubscriptionPlanFeatureAdmin, UserPlanMappingAdmin
from ondoc.doctor.models import (Doctor, Language, MedicalService, Specialization, College, Qualification, Hospital,
                                 HospitalNetwork, DoctorOnboardingToken, OpdAppointment,
                                 MedicalCondition, AboutDoctor, HealthTip, CommonMedicalCondition, CommonSpecialization,
                                 DoctorClinic, DoctorMapping, DoctorImage, OpdAppointment, CompetitorInfo,
                                 SpecializationDepartment, SpecializationField, PracticeSpecialization,
                                 VisitReason, CancellationReason, PracticeSpecializationContent, OfflinePatients,
                                 OfflineOPDAppointments,
                                 DoctorMobileOtp, UploadDoctorData, DoctorLeave, HealthInsuranceProvider,
                                 CommonHospital, SimilarSpecializationGroup, PurchaseOrderCreation, SponsoredServices,
                                 HospitalSponsoredServices, DoctorSponsoredServices,
                                 SponsoredServicePracticeSpecialization, GoogleMapRecords)

from ondoc.diagnostic.models import (Lab, LabNetwork, LabTest, LabTestType, LabService,
                                     AvailableLabTest, LabAppointment, CommonTest, CommonDiagnosticCondition,
                                     LabPricingGroup,
                                     TestParameter, CommonPackage, LabTestCategory, LabTestGroup, LabTestGroupMapping,
                                     TestParameterChat, LabTestCategoryUrls, IPDMedicinePageLead, LabtestNameMaster)
from ondoc.coupon.models import Coupon, UserSpecificCoupon, RandomGeneratedCoupon
from ondoc.integrations.models import IntegratorLabTestParameterMapping
from ondoc.lead.models import HospitalLead, DoctorLead, SearchLead
from ondoc.account.models import ConsumerAccount, MerchantPayout, Order, MerchantPayoutBulkProcess, \
    AdvanceMerchantPayout, AdvanceMerchantAmount
from ondoc.location.admin import EntityUrlsAdmin
from ondoc.location.models import EntityUrls, CompareSEOUrls
from ondoc.notification import models as notifcation_model
from ondoc.notification.models import DynamicTemplates
from ondoc.procedure.models import Procedure, ProcedureCategory, CommonProcedureCategory, CommonProcedure, IpdProcedure, \
    IpdProcedureCategory, CommonIpdProcedure, IpdProcedureDetail, IpdProcedureDetailType, IpdProcedureSynonym, \
    IpdProcedureSynonymMapping, IpdProcedurePracticeSpecialization, IpdProcedureLead, Offer, \
    PotentialIpdLeadPracticeSpecialization, IpdProcedureCostEstimate, \
    IpdCostEstimateRoomType, UploadCostEstimateData, DoctorClinicIpdProcedure, PotentialIpdCity
from ondoc.provider.models import PartnerLabTestSamples, PartnerLabTestSampleDetails, TestSamplesLabAlerts, PartnerLabSamplesCollectOrder

from ondoc.subscription_plan.models import Plan, PlanFeature, UserPlanMapping
from .common import Cities, CitiesAdmin, MatrixCityMapping, MatrixCityAdmin, MerchantAdmin, MerchantPayoutAdmin, \
    PaymentOptionsAdmin, MatrixMappedStateAdmin, MatrixMappedCityAdmin, GlobalNonBookableAdmin, UserConfigAdmin, \
    BlacklistUserAdmin, BlockedStatesAdmin, MerchantPayoutBulkProcessAdmin, AdvanceMerchantPayoutAdmin, \
    AdvanceMerchantAmountAdmin, SearchCriteriaAdmin, GoogleLatLongAdmin
from .lead import HospitalLeadAdmin, DoctorLeadAdmin, SearchLeadAdmin
from .doctor import (DoctorAdmin, MedicalServiceAdmin, SpecializationAdmin, QualificationAdmin, LanguageAdmin,
                     CollegeAdmin, MedicalConditionAdmin, HealthTipAdmin, DoctorClinicAdmin,
                     DoctorMappingAdmin, DoctorImageAdmin, DoctorOpdAppointmentAdmin, CommonSpecializationAdmin,
                     SpecializationFieldAdmin, SpecializationDepartmentAdmin, PracticeSpecializationAdmin,
                     CompetitorInfoImportAdmin, VisitReasonAdmin, PracticeSpecializationContentAdmin,
                     OfflinePatientAdmin,
                     UploadDoctorDataAdmin, DoctorLeaveAdmin, SimilarSpecializationGroupAdmin,
                     PurchaseOrderCreationAdmin, SponsoredServicesAdmin, HospitalSponsoredServicesAdmin,
                     DoctorSponsoredServicesAdmin)
from .aboutdoctor import AboutDoctorAdmin
from .hospital import HospitalAdmin, CommonHospitalAdmin, GenericQuestionAnswerAdmin
from .user import CustomUserAdmin, UserNumberUpdateAdmin, UserProfileAdmin, PermissionAdmin
from .hospital_network import HospitalNetworkAdmin
from .lab import LabAdmin, LabTestAdmin, LabTestTypeAdmin, AvailableLabTestAdmin, CommonDiagnosticConditionAdmin, \
    LabAppointmentAdmin, CommonTestAdmin, TestParameterAdmin, CommonPackageAdmin, LabTestCategoryAdmin, \
    LabTestGroupAdmin, LabTestGroupMappingAdmin, TestParameterChatAdmin, LabTestCategoryUrlsAdmin, \
    LabTestNameMasterAdmin
from .lab_network import LabNetworkAdmin
from .notification import (EmailNotificationAdmin, SmsNotificationAdmin,
                           PushNotificationAdmin, AppNotificationAdmin, DynamicTemplatesAdmin)
from .report import ReportAdmin
from .coupon import CouponAdmin, UserSpecificCouponAdmin, RandomGeneratedCouponAdmin
from .provider import PartnerLabTestSampleAdmin, PartnerLabTestSampleDetailAdmin, TestSamplesLabAlertAdmin, PartnerLabSamplesCollectOrderAdmin
from ondoc.reports import models as report_models
from ondoc.authentication.models import GenericLabAdmin, UserNumberUpdate, GenericQuestionAnswer

from ondoc.web.models import OnlineLead, Career, ContactUs
from django.contrib.auth import get_user_model
from ondoc.authentication.models import OtpVerifications, UserProfile, Merchant, AssociatedMerchant

from ondoc.geoip.models import AdwordLocationCriteria
from .geoip import AdwordLocationCriteriaAdmin
from ondoc.insurance.models import Insurer, InsurerAccount, InsurancePlans, InsuranceThreshold, UserInsurance, \
    InsuredMembers, InsuranceTransaction, InsurancePlanContent, InsuranceDisease, StateGSTCode, InsuranceCity, \
    InsuranceDistrict, InsuranceDeal, InsurerPolicyNumber, InsuranceLead, InsuranceCancelMaster, EndorsementRequest, \
    InsuredMemberDocument, InsuredMemberHistory, InsuranceEligibleCities, ThirdPartyAdministrator, \
    UserBank, UserBankDocument, InsurerAccountTransfer, BankHolidays
from ondoc.crm.admin.insurance import InsurerAdmin, InsurancePlansAdmin, InsuranceThresholdAdmin, InsurerFloatAdmin, \
    UserInsuranceAdmin, InsuredMembersAdmin, InsuranceDiseaseAdmin, StateGSTCodeAdmin, InsuranceCityAdmin, \
    InsuranceDistrictAdmin, InsuranceDealAdmin, InsurerPolicyNumberAdmin, InsuranceLeadAdmin, InsuranceCancelMasterAdmin, \
    EndorsementRequestAdmin, InsuredMemberDocumentAdmin, InsuredMemberHistoryAdmin, InsuranceEligibleCitiesAdmin, \
    ThirdPartyAdministratorAdmin, InsurerAccountTransferAdmin

from ondoc.insurance import models as insurance_model
from ondoc.ratings_review.models import RatingsReview, ReviewCompliments, AppRatings, AppCompliments
from ondoc.crm.admin.ratings import RatingsReviewAdmin, ReviewComplimentsAdmin, AppRatingsAdmin, AppComplimentsAdmin
from ondoc.crm.admin.common import ContactUsAdmin
from ondoc.doctor.models import GoogleDetailing
from .doctor import GoogleDetailingAdmin
from .seo import SitemapManagerAdmin, SeoSpecializationAdmin, SeoLabNetworkAdmin, NewDynamicAdmin
from ondoc.seo.models import SitemapManger, NewDynamic
from ondoc.seo.models import SeoSpecialization
from ondoc.seo.models import SeoLabNetwork
from ondoc.elastic.models import DemoElastic
from .elastic import DemoElasticAdmin
from ondoc.banner.models import Banner, SliderLocation, BannerLocation, EmailBanner, Recommender
from .integrations import IntegratorMapping, IntegratorMappingAdmin, IntegratorHospitalMappings, \
    IntegratorDoctorMappings, IntegratorLabTestParameterMappingAdmin
from .integrations import IntegratorProfileMapping, IntegratorProfileMappingAdmin, IntegratorHospitalMappingsAdmin
from .integrations import IntegratorReport, IntegratorReportAdmin, IntegratorDoctorMappingsAdmin
from .integrations import IntegratorTestMapping, IntegratorTestMappingAdmin
from .integrations import IntegratorTestParameterMapping, IntegratorTestParameterMappingAdmin
from .salespoint import SalesPointAdmin, SalesPointAvailableTestMappingAdmin
from ondoc.salespoint.models import SalesPoint, SalespointTestmapping
from .plus import PlusPlansAdmin, PlusProposerAdmin, PlusThresholdAdmin, PlusUserAdmin, PlusPlanParametersAdmin
from ondoc.plus.models import PlusUser, PlusProposer, PlusPlans, PlusThreshold, PlusPlanParameters, PlusMembers
from .plus import PlusPlansAdmin, PlusProposerAdmin, PlusThresholdAdmin, PlusUserAdmin, PlusPlanParametersAdmin, \
    PlusPlanUtmSourceAdmin, PlusMemberAdmin
from ondoc.plus.models import PlusUser, PlusProposer, PlusPlans, PlusThreshold, PlusPlanParameters, PlusPlanUtmSources
from django.contrib.auth.models import Permission

User = get_user_model()

# Admin Site config
admin.site.site_header = 'Ondoc CRM'
admin.site.site_title = 'Ondoc CRM'
admin.site.site_url = None
admin.site.index_title = 'CRM Administration'


admin.site.register(PlusThreshold, PlusThresholdAdmin)
admin.site.register(PlusPlans, PlusPlansAdmin)
admin.site.register(PlusUser, PlusUserAdmin)
admin.site.register(PlusMembers, PlusMemberAdmin)
admin.site.register(PlusProposer, PlusProposerAdmin)
admin.site.register(PlusPlanParameters, PlusPlanParametersAdmin)
admin.site.register(PlusPlanUtmSources, PlusPlanUtmSourceAdmin)

admin.site.register(OtpVerifications)
# admin.site.register(OpdAppointment)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(ReviewCompliments, ReviewComplimentsAdmin)
admin.site.register(Banner, BannerAdmin)

admin.site.register(LabAppointment, LabAppointmentAdmin)  # temp temp temp
# admin.site.register(DoctorClinic, DoctorClinicAdmin)

admin.site.register(Doctor, DoctorAdmin)
admin.site.register(AboutDoctor, AboutDoctorAdmin)
admin.site.register(DoctorOnboardingToken)
admin.site.register(DoctorImage, DoctorImageAdmin)
admin.site.register(Qualification, QualificationAdmin)
admin.site.register(DoctorMapping, DoctorMappingAdmin)
admin.site.register(Hospital, HospitalAdmin)
admin.site.register(CommonHospital, CommonHospitalAdmin)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Language, LanguageAdmin)
admin.site.register(MedicalService, MedicalServiceAdmin)
admin.site.register(CommonMedicalCondition)
admin.site.register(CommonSpecialization, CommonSpecializationAdmin)
admin.site.register(Specialization, SpecializationAdmin)
admin.site.register(MedicalCondition, MedicalConditionAdmin)
admin.site.register(HealthTip, HealthTipAdmin)
admin.site.register(OfflinePatients, OfflinePatientAdmin)
admin.site.register(OfflineOPDAppointments)
admin.site.register(DoctorLeave, DoctorLeaveAdmin)

admin.site.register(College, CollegeAdmin)
admin.site.register(HospitalNetwork, HospitalNetworkAdmin)
admin.site.register(Lab, LabAdmin)
admin.site.register(CommonTest, CommonTestAdmin)
admin.site.register(CommonPackage, CommonPackageAdmin)
admin.site.register(CommonDiagnosticCondition, CommonDiagnosticConditionAdmin)
admin.site.register(LabNetwork, LabNetworkAdmin)

admin.site.register(LabTest, LabTestAdmin)
admin.site.register(LabTestType, LabTestTypeAdmin)
# admin.site.register(LabTestSubType, LabSubTestTypeAdmin)
admin.site.register(AvailableLabTest, AvailableLabTestAdmin)
admin.site.register(LabTestCategory, LabTestCategoryAdmin)
admin.site.register(LabTestGroup, LabTestGroupAdmin)
admin.site.register(LabTestGroupMapping, LabTestGroupMappingAdmin)

admin.site.register(HospitalLead, HospitalLeadAdmin)
admin.site.register(Cities, CitiesAdmin)
admin.site.register(MatrixMappedState, MatrixMappedStateAdmin)
admin.site.register(MatrixMappedCity, MatrixMappedCityAdmin)
admin.site.register(MatrixCityMapping, MatrixCityAdmin)
admin.site.register(DoctorLead, DoctorLeadAdmin)
admin.site.register(SearchLead, SearchLeadAdmin)

admin.site.register(notifcation_model.EmailNotification, EmailNotificationAdmin)
admin.site.register(notifcation_model.SmsNotification, SmsNotificationAdmin)
admin.site.register(notifcation_model.PushNotification, PushNotificationAdmin)
admin.site.register(notifcation_model.AppNotification, AppNotificationAdmin)
admin.site.register(OpdAppointment, DoctorOpdAppointmentAdmin)
admin.site.register(report_models.Report)
admin.site.register(report_models.GeneratedReport, ReportAdmin)
admin.site.register(SpecializationField, SpecializationFieldAdmin)
admin.site.register(SpecializationDepartment, SpecializationDepartmentAdmin)
admin.site.register(PracticeSpecialization, PracticeSpecializationAdmin)
admin.site.register(ConsumerAccount)
admin.site.register(TestParameter, TestParameterAdmin)
admin.site.register(CompetitorInfo, CompetitorInfoImportAdmin)
admin.site.register(Procedure, ProcedureAdmin)
admin.site.register(Insurer, InsurerAdmin)
admin.site.register(InsuranceThreshold, InsuranceThresholdAdmin)
admin.site.register(InsurancePlans, InsurancePlansAdmin)
admin.site.register(InsurerAccount, InsurerFloatAdmin)
admin.site.register(UserInsurance, UserInsuranceAdmin)
admin.site.register(InsuredMembers, InsuredMembersAdmin)
admin.site.register(InsuranceDisease, InsuranceDiseaseAdmin)
admin.site.register(StateGSTCode, StateGSTCodeAdmin)
admin.site.register(InsuranceCity, InsuranceCityAdmin)
admin.site.register(InsuranceDistrict, InsuranceDistrictAdmin)
admin.site.register(InsuranceDeal, InsuranceDealAdmin)
admin.site.register(InsuranceLead, InsuranceLeadAdmin)
admin.site.register(InsuranceCancelMaster, InsuranceCancelMasterAdmin)
admin.site.register(EndorsementRequest, EndorsementRequestAdmin)
admin.site.register(InsuredMemberDocument, InsuredMemberDocumentAdmin)
admin.site.register(InsuredMemberHistory, InsuredMemberHistoryAdmin)
admin.site.register(InsuranceEligibleCities, InsuranceEligibleCitiesAdmin)
admin.site.register(InsurerAccountTransfer, InsurerAccountTransferAdmin)
# admin.site.register(InsuranceReport, InsuranceReportAdmin)
# admin.site.register(InsurancePlanContent, InsurancePlanContentAdmin)

admin.site.register(InsuranceTransaction)
admin.site.register(InsurerPolicyNumber, InsurerPolicyNumberAdmin)
admin.site.register(UserBank)
admin.site.register(UserBankDocument)
admin.site.register(Order)
admin.site.register(AdwordLocationCriteria, AdwordLocationCriteriaAdmin)
admin.site.register(ProcedureCategory, ProcedureCategoryAdmin)
admin.site.register(RatingsReview, RatingsReviewAdmin)
admin.site.register(SitemapManger, SitemapManagerAdmin)
admin.site.register(GoogleDetailing, GoogleDetailingAdmin)
admin.site.register(Coupon, CouponAdmin)
admin.site.register(UserSpecificCoupon, UserSpecificCouponAdmin)
admin.site.register(RandomGeneratedCoupon, RandomGeneratedCouponAdmin)
admin.site.register(VisitReason, VisitReasonAdmin)
admin.site.register(CancellationReason)
admin.site.register(SeoSpecialization, SeoSpecializationAdmin)

admin.site.register(SeoLabNetwork, SeoLabNetworkAdmin)
admin.site.register(PracticeSpecializationContent, PracticeSpecializationContentAdmin)
admin.site.register(CommonProcedureCategory)
admin.site.register(CommonProcedure)
admin.site.register(DemoElastic, DemoElasticAdmin)
admin.site.register(Merchant, MerchantAdmin)
admin.site.register(MerchantPayout, MerchantPayoutAdmin)
admin.site.register(MerchantPayoutBulkProcess, MerchantPayoutBulkProcessAdmin)
admin.site.register(AdvanceMerchantPayout, AdvanceMerchantPayoutAdmin)
admin.site.register(AdvanceMerchantAmount, AdvanceMerchantAmountAdmin)

# admin.site.register(AssociatedMerchant)
admin.site.register(DoctorMobileOtp)
admin.site.register(NewDynamic, NewDynamicAdmin)
admin.site.register(EntityUrls, EntityUrlsAdmin)
admin.site.register(PaymentOptions, PaymentOptionsAdmin)
admin.site.register(UserConfig, UserConfigAdmin)
admin.site.register(UploadDoctorData, UploadDoctorDataAdmin)
admin.site.register(SimilarSpecializationGroup, SimilarSpecializationGroupAdmin)
admin.site.register(UploadCostEstimateData, UploadCostEstimateDataAdmin)
admin.site.register(SliderLocation, SliderLocationAdmin)
admin.site.register(DoctorClinic, DoctorClinicAdmin)
admin.site.register(IntegratorMapping, IntegratorMappingAdmin)
admin.site.register(IntegratorProfileMapping, IntegratorProfileMappingAdmin)
admin.site.register(IntegratorDoctorMappings, IntegratorDoctorMappingsAdmin)
admin.site.register(IntegratorHospitalMappings, IntegratorHospitalMappingsAdmin)
admin.site.register(GlobalNonBookable, GlobalNonBookableAdmin)
admin.site.register(IpdProcedure, IpdProcedureAdmin)
admin.site.register(IpdProcedureSynonym, IpdProcedureSynonymAdmin)
admin.site.register(IpdProcedureSynonymMapping, IpdProcedureSynonymMappingAdmin)
admin.site.register(IpdProcedureDetailType, IpdProcedureDetailTypeAdmin)
admin.site.register(IpdProcedureDetail, IpdProcedureDetailAdmin)
admin.site.register(IpdProcedurePracticeSpecialization, IpdProcedurePracticeSpecializationAdmin)
admin.site.register(IpdProcedureLead, IpdProcedureLeadAdmin)
admin.site.register(Offer, OfferAdmin)
admin.site.register(PotentialIpdLeadPracticeSpecialization, PotentialIpdLeadPracticeSpecializationAdmin)
admin.site.register(PotentialIpdCity, PotentialIpdCityAdmin)
admin.site.register(IpdProcedureCostEstimate, IpdProcedureCostEstimateAdmin)
admin.site.register(IpdCostEstimateRoomType, IpdCostEstimateRoomTypeAdmin)
admin.site.register(Feature, FeatureAdmin)
admin.site.register(Service, ServiceAdmin)
admin.site.register(HealthInsuranceProvider, HealthInsuranceProviderAdmin)
admin.site.register(IntegratorReport, IntegratorReportAdmin)
admin.site.register(IntegratorTestMapping, IntegratorTestMappingAdmin)
admin.site.register(IntegratorTestParameterMapping, IntegratorTestParameterMappingAdmin)
admin.site.register(IpdProcedureCategory, IpdProcedureCategoryAdmin)
admin.site.register(CommonIpdProcedure)
admin.site.register(Plan, SubscriptionPlanAdmin)
admin.site.register(PlanFeature, SubscriptionPlanFeatureAdmin)
admin.site.register(UserPlanMapping, UserPlanMappingAdmin)
admin.site.register(TestParameterChat, TestParameterChatAdmin)
admin.site.register(SalesPoint, SalesPointAdmin)
admin.site.register(SalespointTestmapping, SalesPointAvailableTestMappingAdmin)
admin.site.register(AppRatings, AppRatingsAdmin)
admin.site.register(AppCompliments, AppComplimentsAdmin)
admin.site.register(ContactUs, ContactUsAdmin)
admin.site.register(Corporates, CorporatesAdmin)
admin.site.register(CorporateDeal, CorporateDealAdmin)
admin.site.register(CompareSEOUrls, ComparePackagesSEOUrlsAdmin)
admin.site.register(BannerLocation)
admin.site.register(EmailBanner, EmailBannerAdmin)
admin.site.register(Recommender, RecommenderAdmin)
admin.site.register(ThirdPartyAdministrator, ThirdPartyAdministratorAdmin)
admin.site.register(BlacklistUser, BlacklistUserAdmin)
admin.site.register(BlockedStates, BlockedStatesAdmin )
admin.site.register(BankHolidays)
admin.site.register(LabTestCategoryUrls, LabTestCategoryUrlsAdmin)
admin.site.register(UserNumberUpdate, UserNumberUpdateAdmin)
admin.site.register(GenericQuestionAnswer, GenericQuestionAnswerAdmin)
admin.site.register(IntegratorLabTestParameterMapping, IntegratorLabTestParameterMappingAdmin)
admin.site.register(PurchaseOrderCreation, PurchaseOrderCreationAdmin)
admin.site.register(SponsorListingURL)
admin.site.register(SponsorListingSpecialization)
admin.site.register(SponsorListingUtmTerm)
admin.site.register(SponsoredListingService)
admin.site.register(DynamicTemplates, DynamicTemplatesAdmin)
admin.site.register(SponsoredServices, SponsoredServicesAdmin)
admin.site.register(IPDMedicinePageLead)
admin.site.register(HospitalSponsoredServices, HospitalSponsoredServicesAdmin)
admin.site.register(DoctorSponsoredServices, DoctorSponsoredServicesAdmin)
admin.site.register(SponsoredServicePracticeSpecialization)
admin.site.register(PartnerLabTestSamples, PartnerLabTestSampleAdmin)
admin.site.register(PartnerLabTestSampleDetails, PartnerLabTestSampleDetailAdmin)
admin.site.register(TestSamplesLabAlerts, TestSamplesLabAlertAdmin)
admin.site.register(PartnerLabSamplesCollectOrder, PartnerLabSamplesCollectOrderAdmin)
admin.site.register(SearchCriteria, SearchCriteriaAdmin)
admin.site.register(Permission, PermissionAdmin)
admin.site.register(Certifications)
admin.site.register(GoogleMapRecords)
admin.site.register(LabtestNameMaster, LabTestNameMasterAdmin)
admin.site.register(GoogleLatLong, GoogleLatLongAdmin)
