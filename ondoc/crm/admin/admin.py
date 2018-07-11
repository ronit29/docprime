

from django.contrib.gis import admin

from ondoc.doctor.models import (Doctor, Language, MedicalService, Specialization, College, Qualification, Hospital,
                                 HospitalNetwork, DoctorOnboardingToken, OpdAppointment, GeneralSpecialization,
                                 MedicalCondition, AboutDoctor, HealthTip)
from ondoc.diagnostic.models import (Lab, LabNetwork, LabTest, LabTestType,LabService,
                                      AvailableLabTest, LabAppointment)
from ondoc.lead.models import HospitalLead, DoctorLead
from ondoc.notification import models as notifcation_model
from .lead import HospitalLeadAdmin, DoctorLeadAdmin
from .doctor import (DoctorAdmin, MedicalServiceAdmin, SpecializationAdmin, QualificationAdmin, LanguageAdmin,
                     CollegeAdmin, GeneralSpecializationAdmin, MedicalConditionAdmin, HealthTipAdmin)
from .aboutdoctor import AboutDoctorAdmin
from .hospital import HospitalAdmin
from .user import CustomUserAdmin
from .hospital_network import HospitalNetworkAdmin
from .lab import LabAdmin, LabTestAdmin, LabTestTypeAdmin, AvailableLabTestAdmin
from .lab_network import LabNetworkAdmin
from .notification import (EmailNotificationAdmin, SmsNotificationAdmin,
                           PushNotificationAdmin, AppNotificationAdmin)

from ondoc.web.models import OnlineLead, Career
from django.contrib.auth import get_user_model
User = get_user_model()
from ondoc.authentication.models import OtpVerifications, UserProfile


# Admin Site config
admin.site.site_header = 'Ondoc CRM'
admin.site.site_title = 'Ondoc CRM'
admin.site.site_url = None
admin.site.index_title = 'CRM Administration'



admin.site.register(OtpVerifications)
admin.site.register(OpdAppointment)
admin.site.register(UserProfile)

admin.site.register(LabAppointment) #temp temp temp

admin.site.register(Doctor, DoctorAdmin)
admin.site.register(AboutDoctor, AboutDoctorAdmin)
admin.site.register(DoctorOnboardingToken)
admin.site.register(Qualification, QualificationAdmin)
# admin.site.register(Specialization)
admin.site.register(Hospital, HospitalAdmin)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Language, LanguageAdmin)
admin.site.register(MedicalService, MedicalServiceAdmin)
# admin.site.register(DoctorMedicalService)
admin.site.register(Specialization, SpecializationAdmin)
admin.site.register(GeneralSpecialization, GeneralSpecializationAdmin)
admin.site.register(MedicalCondition, MedicalConditionAdmin)
admin.site.register(HealthTip, HealthTipAdmin)

admin.site.register(College, CollegeAdmin)
admin.site.register(HospitalNetwork, HospitalNetworkAdmin)
admin.site.register(Lab, LabAdmin)
admin.site.register(LabNetwork, LabNetworkAdmin)

admin.site.register(LabTest, LabTestAdmin)
admin.site.register(LabTestType, LabTestTypeAdmin)
#admin.site.register(LabTestSubType, LabSubTestTypeAdmin)
admin.site.register(AvailableLabTest, AvailableLabTestAdmin)

admin.site.register(HospitalLead, HospitalLeadAdmin)
admin.site.register(DoctorLead, DoctorLeadAdmin)

admin.site.register(notifcation_model.EmailNotification, EmailNotificationAdmin)
admin.site.register(notifcation_model.SmsNotification, SmsNotificationAdmin)
admin.site.register(notifcation_model.PushNotification, PushNotificationAdmin)
admin.site.register(notifcation_model.AppNotification, AppNotificationAdmin)
