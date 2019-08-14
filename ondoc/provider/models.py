from django.db import models, transaction
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from ondoc.common import models as common_models
from ondoc.account import models as acct_mdoels
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import JSONField
import logging, json, uuid
logger = logging.getLogger(__name__)
from django.conf import settings
from ondoc.api.v1 import utils as v1_utils

# Create your models here.

class RocketChatUsers(auth_models.TimeStampedModel):

    # AUTH_TOKEN = 'Bwil0I0XK5GtRTuxFMaxxolZ-mNtQ-40MOjjcV6uzF8'
    # AUTH_USER_ID = '8DjvhTsfjxFHpuLcR'

    AUTH_TOKEN = 'jtJnQp40Z1ZzFWd7zftbsfXfkT60K3P7MQlZpIS5CZ_'
    AUTH_USER_ID = 'RX2J45QQShWpxgtNd'

    name = models.CharField(max_length=64)
    email = models.EmailField(max_length=64, unique=True)
    password = models.CharField(max_length=64)
    username = models.CharField(max_length=64, unique=True)
    rc_req_extras = JSONField()
    response_data = JSONField()
    user_type = models.PositiveSmallIntegerField(choices=((auth_models.User.DOCTOR, 'doctor'),
                                                          (auth_models.User.CONSUMER, 'user')))
    doctor = models.ForeignKey(doc_models.Doctor, related_name='rc_user', on_delete=models.SET_NULL, null=True)
    offline_patient = models.ForeignKey(doc_models.OfflinePatients, related_name='rc_user', on_delete=models.SET_NULL, null=True)
    online_patient = models.ForeignKey(auth_models.UserProfile, related_name='rc_user', on_delete=models.SET_NULL, null=True)
    login_token = models.CharField(max_length=64)

    @staticmethod
    def create_rc_user_and_login_token(auth_token, auth_user_id, patient=None, doctor=None):
        rocket_chat_user_obj = e = None
        try:
            if patient:
                name = patient.name
                user_type = auth_models.User.CONSUMER
            elif doctor:
                name = doctor.name
                user_type = auth_models.User.DOCTOR
            else:
                raise Exception('either patient or doctor is required for creating rc_user')
            rc_req_extras = {'user_type': user_type}
            created_user_dict = v1_utils.rc_user_create(auth_token, auth_user_id, name, rc_req_extras=rc_req_extras)
            username = created_user_dict.get('username')
            login_token = v1_utils.rc_user_login(auth_token, auth_user_id, username)['data']['authToken']

            if user_type == auth_models.User.DOCTOR:
                created_user_dict['doctor'] = doctor
            elif v1_utils.is_valid_uuid(patient.id):
                created_user_dict['offline_patient'] = patient
            else:
                created_user_dict['online_patient'] = patient
            rocket_chat_user_obj = RocketChatUsers.objects.create(**created_user_dict, login_token=login_token,
                                                                  user_type=user_type)
        except Exception as e:
            return rocket_chat_user_obj, e
        return rocket_chat_user_obj, e

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
        url_common_address = settings.ROCKETCHAT_SERVER + '/group/' + self.group.name + '?layout=embedded&autoLogin=true&loginToken='
        self.patient_login_url = url_common_address + patient_login_token
        self.doctor_login_url = url_common_address + doctor_login_token
        return self

    @classmethod
    def create_group(cls, auth_token, auth_user_id, rc_patient, rc_doctor):
        rc_group_obj = e = None
        try:
            response_data_dict = v1_utils.rc_group_create(auth_token, auth_user_id, rc_patient.username, rc_doctor.username)
            if response_data_dict['success']:
                group_id = response_data_dict['group']['_id']
                group_name = response_data_dict['group']['name']
                rc_group_obj = cls(group_id=group_id, group_name=group_name, data=response_data_dict)
                rc_group_obj.create_auto_login_link(rc_patient.login_token, rc_doctor.login_token)
                rc_group_obj.save()
            else:
                raise Exception(response_data_dict['error'])
        except Exception as e:
            return rc_group_obj, e
        return rc_group_obj, e

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

    @classmethod
    def update_consultation(self, data):
        self.payment_status = self.PAYMENT_ACCEPTED
        self.status = self.BOOKED

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
            EConsultation.objects.filter(id=self.id).update(link=link)
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


    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = "e_consultation"
