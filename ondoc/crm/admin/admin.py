
from django.contrib.gis import admin

from ondoc.crm.admin.procedure import ProcedureCategoryAdmin, ProcedureAdmin
from ondoc.doctor.models import (Doctor, Language, MedicalService, Specialization, College, Qualification, Hospital,
                                 HospitalNetwork, DoctorOnboardingToken, OpdAppointment,
                                 MedicalCondition, AboutDoctor, HealthTip, CommonMedicalCondition, CommonSpecialization,
                                 DoctorClinic, DoctorMapping, DoctorImage, OpdAppointment, CompetitorInfo,
                                 SpecializationDepartment, SpecializationField, PracticeSpecialization,
                                 VisitReason, CancellationReason, PracticeSpecializationContent)
from ondoc.diagnostic.models import (Lab, LabNetwork, LabTest, LabTestType,LabService,
                                      AvailableLabTest, LabAppointment, CommonTest, CommonDiagnosticCondition, LabPricingGroup,
                                     TestParameter, CommonPackage)
from ondoc.coupon.models import Coupon
from ondoc.lead.models import HospitalLead, DoctorLead, SearchLead
from ondoc.account.models import ConsumerAccount
from ondoc.notification import models as notifcation_model
from ondoc.procedure.models import Procedure, ProcedureCategory
from .common import Cities, CitiesAdmin, MatrixCityMapping, MatrixCityAdmin
from .lead import HospitalLeadAdmin, DoctorLeadAdmin, SearchLeadAdmin
from .doctor import (DoctorAdmin, MedicalServiceAdmin, SpecializationAdmin, QualificationAdmin, LanguageAdmin,
                     CollegeAdmin, MedicalConditionAdmin, HealthTipAdmin, DoctorClinicAdmin,
                     DoctorMappingAdmin, DoctorImageAdmin, DoctorOpdAppointmentAdmin, CommonSpecializationAdmin,
                     SpecializationFieldAdmin, SpecializationDepartmentAdmin, PracticeSpecializationAdmin,
                     CompetitorInfoImportAdmin, VisitReasonAdmin, PracticeSpecializationContentAdmin)
from .aboutdoctor import AboutDoctorAdmin
from .hospital import HospitalAdmin
from .user import CustomUserAdmin
from .hospital_network import HospitalNetworkAdmin
from .lab import LabAdmin, LabTestAdmin, LabTestTypeAdmin, AvailableLabTestAdmin, CommonDiagnosticConditionAdmin, \
    LabAppointmentAdmin, CommonTestAdmin, TestParameterAdmin, CommonPackageAdmin
from .lab_network import LabNetworkAdmin
from .notification import (EmailNotificationAdmin, SmsNotificationAdmin,
                           PushNotificationAdmin, AppNotificationAdmin)
from .report import ReportAdmin
from ondoc.reports import models as report_models
from ondoc.authentication.models import GenericLabAdmin

from ondoc.web.models import OnlineLead, Career
from django.contrib.auth import get_user_model

User = get_user_model()
from ondoc.authentication.models import OtpVerifications, UserProfile

from ondoc.geoip.models import AdwordLocationCriteria
from .geoip import AdwordLocationCriteriaAdmin
from ondoc.ratings_review.models import RatingsReview, ReviewCompliments
from ondoc.crm.admin.ratings import RatingsReviewAdmin, ReviewComplimentsAdmin
from ondoc.doctor.models import GoogleDetailing
from .doctor import GoogleDetailingAdmin
from .seo import SitemapManagerAdmin, SeoSpecializationAdmin, SeoLabNetworkAdmin
from ondoc.seo.models import SitemapManger
from ondoc.seo.models import SeoSpecialization
from ondoc.seo.models import SeoLabNetwork

# Admin Site config
admin.site.site_header = 'Ondoc CRM'
admin.site.site_title = 'Ondoc CRM'
admin.site.site_url = None
admin.site.index_title = 'CRM Administration'


admin.site.register(OtpVerifications)
# admin.site.register(OpdAppointment)
admin.site.register(UserProfile)
admin.site.register(ReviewCompliments, ReviewComplimentsAdmin)

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

admin.site.register(HospitalLead, HospitalLeadAdmin)
admin.site.register(Cities, CitiesAdmin)
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
admin.site.register(Coupon)
admin.site.register(VisitReason, VisitReasonAdmin)
admin.site.register(CancellationReason)
admin.site.register(SeoSpecialization, SeoSpecializationAdmin)

admin.site.register(SeoLabNetwork, SeoLabNetworkAdmin)
admin.site.register(PracticeSpecializationContent, PracticeSpecializationContentAdmin)
