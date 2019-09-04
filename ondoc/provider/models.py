from django.db import models, transaction
from ondoc.doctor import models as doc_models
from ondoc.diagnostic import models as diag_models
from ondoc.authentication import models as auth_models
from ondoc.common import models as common_models
from ondoc.account import models as acct_mdoels
from ondoc.prescription import models as pres_models
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import JSONField
import logging, json, uuid, requests
logger = logging.getLogger(__name__)
from django.conf import settings
from ondoc.api.v1 import utils as v1_utils
from rest_framework import status

# Create your models here.

class RocketChatSuperUser(auth_models.TimeStampedModel):
    username = models.CharField(max_length=64)
    password = models.CharField(max_length=64)
    user_id = models.CharField(max_length=64, null=True, blank=True)
    token = models.CharField(max_length=64, null=True, blank=True)

    @classmethod
    def update_rc_super_user(cls):
        rc_super_user_obj = cls.objects.order_by('-created_at').first()
        if rc_super_user_obj:
            rc_super_user_obj = v1_utils.rc_superuser_login(rc_super_user_obj=rc_super_user_obj)
        else:
            rc_super_user_obj = v1_utils.rc_superuser_login()
        return rc_super_user_obj

    def __str__(self):
        return self.username

    class Meta:
        db_table = "rc_super_user"

class RocketChatUsers(auth_models.TimeStampedModel):

    name = models.CharField(max_length=64)
    email = models.EmailField(max_length=64, unique=True)
    password = models.CharField(max_length=64)
    username = models.CharField(max_length=64, unique=True)
    rc_req_extras = JSONField()
    response_data = JSONField()
    user_type = models.PositiveSmallIntegerField(choices=((auth_models.User.DOCTOR, 'doctor'),
                                                          (auth_models.User.CONSUMER, 'user')))
    doctor = models.OneToOneField(doc_models.Doctor, related_name='rc_user', on_delete=models.SET_NULL, null=True)
    offline_patient = models.OneToOneField(doc_models.OfflinePatients, related_name='rc_user', on_delete=models.SET_NULL, null=True)
    online_patient = models.OneToOneField(auth_models.UserProfile, related_name='rc_user', on_delete=models.SET_NULL, null=True)
    login_token = models.CharField(max_length=64)

    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = "rc_users"


class RocketChatGroups(auth_models.TimeStampedModel):

    group_id = models.CharField(max_length=64)
    group_name = models.CharField(max_length=128)
    data = JSONField()
    patient_login_url = models.URLField()
    doctor_login_url = models.URLField()

    def create_auto_login_link(self, patient_login_token, doctor_login_token):
        url_common_address = settings.ROCKETCHAT_SERVER + '/group/' + self.group_name + '?layout=embedded&autoLogin=true&loginToken='
        self.patient_login_url = url_common_address + patient_login_token
        self.doctor_login_url = url_common_address + doctor_login_token
        return self

    @classmethod
    def create_group(cls, auth_token, auth_user_id, patient, rc_doctor):
        response_data_dict = v1_utils.rc_group_create(auth_token, auth_user_id, patient, rc_doctor)
        if not response_data_dict:
            logger.error("Error in creating RC group")
            return None
        group_id = response_data_dict['group']['_id']
        group_name = response_data_dict['group']['name']
        rc_group_obj = cls(group_id=group_id, group_name=group_name, data=response_data_dict)
        rc_group_obj.create_auto_login_link(patient.rc_user.login_token, rc_doctor.login_token)
        rc_group_obj.save()
        return rc_group_obj

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = "rc_groups"


class EConsultation(auth_models.TimeStampedModel, auth_models.CreatedByModel):

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, 'Payment Accepted'),
        (PAYMENT_PENDING, 'Payment Pending'),
    )

    CREATED = 1
    BOOKED = 2
    RESCHEDULED_DOCTOR = 3
    RESCHEDULED_PATIENT = 4
    ACCEPTED = 5
    CANCELLED = 6
    COMPLETED = 7
    EXPIRED = 8
    STATUS_CHOICES = [(CREATED, 'Created'), (BOOKED, 'Booked'),
                      (RESCHEDULED_DOCTOR, 'Rescheduled by Doctor'),
                      (RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                      (ACCEPTED, 'Accepted'), (CANCELLED, 'Cancelled'),
                      (COMPLETED, 'Completed'), (EXPIRED, 'Expired')]

    doctor = models.ForeignKey(doc_models.Doctor, related_name='econsultations', on_delete=models.SET_NULL, null=True)
    offline_patient = models.ForeignKey(doc_models.OfflinePatients, related_name='econsultations', on_delete=models.SET_NULL, null=True)
    online_patient = models.ForeignKey(auth_models.UserProfile, related_name='econsultations', on_delete=models.SET_NULL, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2)
    validity = models.DateTimeField(null=True, blank=True)
    link = models.CharField(max_length=256, null=True, blank=True)
    status = models.PositiveSmallIntegerField(default=CREATED, choices=STATUS_CHOICES)

    #payment Fields
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    refund_details = GenericRelation(common_models.RefundDetails, related_query_name="reconsult_refund_details")
    coupon_data = JSONField(blank=True, null=True)
    money_pool = models.ForeignKey(acct_mdoels.MoneyPool, on_delete=models.SET_NULL, null=True, related_name='econsult_pool')
    price_data = JSONField(blank=True, null=True)
    merchant_payout = models.ForeignKey(acct_mdoels.MerchantPayout, related_name="econsultations", on_delete=models.SET_NULL, null=True)
    rc_group = models.ForeignKey(RocketChatGroups, related_name='econsultations', on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(auth_models.User, on_delete=models.SET_NULL, null=True, related_name="econsultationss")
    prescription_file = GenericRelation(pres_models.AppointmentPrescription, related_query_name='econsult_pres_file')

    def update_consultation(self):
        self.payment_status = self.PAYMENT_ACCEPTED
        self.status = self.BOOKED

    def get_video_chat_url(self):
        return settings.JITSI_SERVER + "/" + self.rc_group.group_id

    def get_patient_and_number(self):
        if self.offline_patient:
            patient = self.offline_patient
            patient_number = str(self.offline_patient.get_patient_mobile())
        else:
            patient = self.online_patient
            patient_number = self.online_patient.phone_number
        return patient, patient_number

    def send_sms_link(self, patient, patient_number):
        from ondoc.authentication.backends import JWTAuthentication
        from ondoc.communications.models import  SMSNotification, NotificationAction

        link = None

        if not self.link:
            if not patient.user:
                user = auth_models.User.objects.filter(phone_number=patient_number, user_type=auth_models.User.CONSUMER).first()
                if not user:
                    user = auth_models.User.objects.create(phone_number=patient_number, user_type=auth_models.User.CONSUMER, auto_created=True)
                patient.user = user
                patient.save()
            else:
                user = patient.user
            agent_token = JWTAuthentication.generate_token(user)
            token = agent_token['token'] if 'token' in agent_token else None
            url = settings.BASE_URL + "/econsult?id=" + str(self.id) + "&token=" + token.decode("utf-8")
            link = v1_utils.generate_short_url(url)
            # self.link = link
            EConsultation.objects.filter(id=self.id).update(link=link, user=user)
        else:
            link = self.link

        receivers = [{"user": None, "phone_number": patient_number}]
        context = {'patient_name': patient.name,
                   'link': link}
        try:
            sms_obj = SMSNotification(notification_type=NotificationAction.E_CONSULT_SHARE, context=context)
            sms_obj.send(receivers=receivers)
        except Exception as e:
            logger.error(str(e))
            return {'error': str(e)}
        return {}

    def post_chat_message(self, user_id, user_token, request_data):
        response = requests.post(settings.ROCKETCHAT_SERVER + '/api/v1/chat.postMessage',
                                 headers={'X-Auth-Token': user_token,
                                          'X-User-Id': user_id,
                                          'Content-Type': 'application/json'},
                                 data=json.dumps(request_data))
        error_message = None
        if response.status_code != status.HTTP_200_OK or not response.ok:
            error_message = "[ERROR] Error in Rocket Chat API hit with user_id - {} and user_token - {}".format(
                user_id, user_token)
            logger.error(
                "Payload - " + json.dumps(request_data) + ", RC Response - " + json.dumps(
                    response.json() + ", response text" + response.text))
        return response, error_message

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = "e_consultation"


class ProviderHospitalLabMapping(models.Model):
    hospital = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE, related_name="provider_labs")
    lab = models.ForeignKey(diag_models.Lab, on_delete=models.CASCADE, related_name="provider_hospitals")

    def __str__(self):
        return str(self.hospital.name) + '-' + str(self.lab.name)

    class Meta:
        db_table = "provider_hospital_lab_mapping"
