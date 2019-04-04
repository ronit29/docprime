
from django.contrib.gis import admin
from ondoc.common.models import PaymentOptions, UserConfig, Feature, Service, MatrixMappedState, MatrixMappedCity, GlobalNonBookable
from ondoc.crm.admin.banner import BannerAdmin, SliderLocationAdmin
from ondoc.crm.admin.procedure import ProcedureCategoryAdmin, ProcedureAdmin, IpdProcedureAdmin, FeatureAdmin, \
    ServiceAdmin, HealthInsuranceProviderAdmin, IpdProcedureCategoryAdmin, IpdProcedureDetailAdmin, \
    IpdProcedureDetailTypeAdmin
from ondoc.crm.admin.subscription_plan import SubscriptionPlanAdmin, SubscriptionPlanFeatureAdmin, UserPlanMappingAdmin
from ondoc.doctor.models import (Doctor, Language, MedicalService, Specialization, College, Qualification, Hospital,
                                 HospitalNetwork, DoctorOnboardingToken, OpdAppointment,
                                 MedicalCondition, AboutDoctor, HealthTip, CommonMedicalCondition, CommonSpecialization,
                                 DoctorClinic, DoctorMapping, DoctorImage, OpdAppointment, CompetitorInfo,
                                 SpecializationDepartment, SpecializationField, PracticeSpecialization,
                                 VisitReason, CancellationReason, PracticeSpecializationContent, OfflinePatients,
                                 OfflineOPDAppointments,
                                 DoctorMobileOtp, UploadDoctorData, DoctorLeave, HealthInsuranceProvider)

from ondoc.diagnostic.models import (Lab, LabNetwork, LabTest, LabTestType,LabService,
                                      AvailableLabTest, LabAppointment, CommonTest, CommonDiagnosticCondition, LabPricingGroup,
                                     TestParameter, CommonPackage, LabTestCategory, LabTestGroup, LabTestGroupMapping,
                                     TestParameterChat)
from ondoc.coupon.models import Coupon, UserSpecificCoupon, RandomGeneratedCoupon
from ondoc.lead.models import HospitalLead, DoctorLead, SearchLead
from ondoc.account.models import ConsumerAccount, MerchantPayout
from ondoc.location.admin import EntityUrlsAdmin
from ondoc.location.models import EntityUrls
from ondoc.notification import models as notifcation_model
from ondoc.procedure.models import Procedure, ProcedureCategory, CommonProcedureCategory, CommonProcedure, IpdProcedure, \
    IpdProcedureCategory, CommonIpdProcedure, IpdProcedureDetail, IpdProcedureDetailType
from ondoc.subscription_plan.models import Plan, PlanFeature, UserPlanMapping
from .common import Cities, CitiesAdmin, MatrixCityMapping, MatrixCityAdmin, MerchantAdmin, MerchantPayoutAdmin, \
    PaymentOptionsAdmin, MatrixMappedStateAdmin, MatrixMappedCityAdmin, GlobalNonBookableAdmin
from .lead import HospitalLeadAdmin, DoctorLeadAdmin, SearchLeadAdmin
from .doctor import (DoctorAdmin, MedicalServiceAdmin, SpecializationAdmin, QualificationAdmin, LanguageAdmin,
                     CollegeAdmin, MedicalConditionAdmin, HealthTipAdmin, DoctorClinicAdmin,
                     DoctorMappingAdmin, DoctorImageAdmin, DoctorOpdAppointmentAdmin, CommonSpecializationAdmin,
                     SpecializationFieldAdmin, SpecializationDepartmentAdmin, PracticeSpecializationAdmin,
                     CompetitorInfoImportAdmin, VisitReasonAdmin, PracticeSpecializationContentAdmin,
                     OfflinePatientAdmin,
                     UploadDoctorDataAdmin, DoctorLeaveAdmin)
from .aboutdoctor import AboutDoctorAdmin
from .hospital import HospitalAdmin
from .user import CustomUserAdmin
from .hospital_network import HospitalNetworkAdmin
from .lab import LabAdmin, LabTestAdmin, LabTestTypeAdmin, AvailableLabTestAdmin, CommonDiagnosticConditionAdmin, \
    LabAppointmentAdmin, CommonTestAdmin, TestParameterAdmin, CommonPackageAdmin, LabTestCategoryAdmin, \
    LabTestGroupAdmin, LabTestGroupMappingAdmin, TestParameterChatAdmin
from .lab_network import LabNetworkAdmin
from .notification import (EmailNotificationAdmin, SmsNotificationAdmin,
                           PushNotificationAdmin, AppNotificationAdmin)
from .report import ReportAdmin
from .coupon import CouponAdmin, UserSpecificCouponAdmin, RandomGeneratedCouponAdmin
from ondoc.reports import models as report_models
from ondoc.authentication.models import GenericLabAdmin

from ondoc.web.models import OnlineLead, Career
from django.contrib.auth import get_user_model

User = get_user_model()
from ondoc.authentication.models import OtpVerifications, UserProfile, Merchant, AssociatedMerchant

from ondoc.geoip.models import AdwordLocationCriteria
from .geoip import AdwordLocationCriteriaAdmin
from ondoc.ratings_review.models import RatingsReview, ReviewCompliments
from ondoc.crm.admin.ratings import RatingsReviewAdmin, ReviewComplimentsAdmin
from ondoc.doctor.models import GoogleDetailing
from .doctor import GoogleDetailingAdmin
from .seo import SitemapManagerAdmin, SeoSpecializationAdmin, SeoLabNetworkAdmin, NewDynamicAdmin
from ondoc.seo.models import SitemapManger, NewDynamic
from ondoc.seo.models import SeoSpecialization
from ondoc.seo.models import SeoLabNetwork
from ondoc.elastic.models import DemoElastic
from .elastic import DemoElasticAdmin
from ondoc.banner.models import Banner, SliderLocation
from .integrations import IntegratorMapping, IntegratorMappingAdmin
from .integrations import IntegratorProfileMapping, IntegratorProfileMappingAdmin
from .integrations import IntegratorReport, IntegratorReportAdmin
from .integrations import IntegratorTestMapping, IntegratorTestMappingAdmin
from .integrations import IntegratorTestParameterMapping, IntegratorTestParameterMappingAdmin
from .salespoint import SalesPointAdmin, SalesPointAvailableTestMappingAdmin
from ondoc.salespoint.models import SalesPoint, SalespointTestmapping

# Admin Site config
admin.site.site_header = 'Ondoc CRM'
admin.site.site_title = 'Ondoc CRM'
admin.site.site_url = None
admin.site.index_title = 'CRM Administration'


admin.site.register(OtpVerifications)
# admin.site.register(OpdAppointment)
admin.site.register(UserProfile)
admin.site.register(ReviewCompliments, ReviewComplimentsAdmin)
admin.site.register(Banner, BannerAdmin)

admin.site.register(LabAppointment, LabAppointmentAdmin) #temp temp temp
#admin.site.register(DoctorClinic, DoctorClinicAdmin)

admin.site.register(Doctor, DoctorAdmin)
admin.site.register(AboutDoctor, AboutDoctorAdmin)
admin.site.register(DoctorOnboardingToken)
admin.site.register(DoctorImage, DoctorImageAdmin)
admin.site.register(Qualification, QualificationAdmin)
admin.site.register(DoctorMapping, DoctorMappingAdmin)
admin.site.register(Hospital, HospitalAdmin)
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
#admin.site.register(LabTestSubType, LabSubTestTypeAdmin)
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
admin.site.register(ProcedureCategory, ProcedureCategoryAdmin)


admin.site.register(AdwordLocationCriteria, AdwordLocationCriteriaAdmin)
admin.site.register(RatingsReview, RatingsReviewAdmin)
admin.site.register(SitemapManger, SitemapManagerAdmin)
admin.site.register(GoogleDetailing, GoogleDetailingAdmin)
admin.site.register(Coupon, CouponAdmin)
admin.site.register(UserSpecificCoupon, UserSpecificCouponAdmin)
# admin.site.register(RandomGeneratedCoupon, RandomGeneratedCouponAdmin)
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
#admin.site.register(AssociatedMerchant)
admin.site.register(DoctorMobileOtp)
admin.site.register(NewDynamic, NewDynamicAdmin)
admin.site.register(EntityUrls, EntityUrlsAdmin)
admin.site.register(PaymentOptions, PaymentOptionsAdmin)
admin.site.register(UserConfig)
admin.site.register(UploadDoctorData, UploadDoctorDataAdmin)
admin.site.register(SliderLocation, SliderLocationAdmin)
admin.site.register(IntegratorMapping, IntegratorMappingAdmin)
admin.site.register(IntegratorProfileMapping, IntegratorProfileMappingAdmin)
admin.site.register(GlobalNonBookable, GlobalNonBookableAdmin)
admin.site.register(IpdProcedure, IpdProcedureAdmin)
admin.site.register(IpdProcedureDetailType, IpdProcedureDetailTypeAdmin)
admin.site.register(IpdProcedureDetail, IpdProcedureDetailAdmin)
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
