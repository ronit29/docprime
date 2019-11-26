from django.db import models, transaction
from django.core.validators import FileExtensionValidator

from ondoc.authentication.models import TransactionMixin
from ondoc.doctor import models as doc_models
from ondoc.diagnostic import models as diag_models
from ondoc.authentication import models as auth_models
from ondoc.common import models as common_models
from ondoc.account import models as acct_mdoels
from ondoc.prescription import models as pres_models
from ondoc.notification.models import NotificationAction
from ondoc.notification import tasks as notification_tasks
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


class EConsultation(auth_models.TimeStampedModel, auth_models.CreatedByModel, TransactionMixin):

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


class PartnerHospitalLabMapping(auth_models.TimeStampedModel):
    hospital = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE, related_name="partner_labs")
    lab = models.ForeignKey(diag_models.Lab, on_delete=models.CASCADE, related_name="partner_hospitals")

    def __str__(self):
        return str(self.lab.name)

    class Meta:
        db_table = "partner_hospital_lab_mapping"


class TestSamplesLabAlerts(auth_models.TimeStampedModel):

    name = models.CharField(max_length=128)

    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = "test_samples_lab_alerts"


class PartnerLabTestSamples(auth_models.TimeStampedModel):

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=128, null=True, blank=True)

    def __str__(self):
        if self.code:
            return str(self.name) + '(' + str(self.code) + ')'
        return str(self.name)

    class Meta:
        db_table = "partner_lab_test_samples"


class PartnerLabTestSampleDetails(auth_models.TimeStampedModel):
    ML = 'ml'
    MG = 'mg'
    VOLUME_UNIT_CHOICES = [(ML, "ml"), (MG, "mg")]
    available_lab_test = models.ForeignKey(diag_models.AvailableLabTest, on_delete=models.CASCADE, related_name="sample_details")
    sample = models.ForeignKey(PartnerLabTestSamples, on_delete=models.CASCADE, related_name="details")
    volume = models.PositiveIntegerField(null=True, blank=True)
    volume_unit = models.CharField(max_length=16, default=None, null=True, blank=True, choices=VOLUME_UNIT_CHOICES)
    is_fasting_required = models.BooleanField(default=False)
    report_tat = models.PositiveSmallIntegerField(null=True, blank=True)                    # in hours
    reference_value = models.TextField(blank=True, null=True)
    material_required = JSONField(blank=True, null=True)
    instructions = models.TextField(null=True, blank=True)

    def __str__(self):
        return str(self.available_lab_test.test.name) + '-' + str(self.sample.name)

    @classmethod
    def get_sample_collection_details(cls, available_lab_tests):
        sample_details = list()
        collection_sample_objs = list()
        sample_max_volumes = dict()
        for obj in available_lab_tests:
            sample_details.extend(obj.sample_details.all())
        for sample_detail in sample_details:
            if sample_detail.sample.name not in sample_max_volumes or \
                    (sample_detail.sample.name in sample_max_volumes and sample_detail.volume and
                     ((not sample_max_volumes[sample_detail.sample.name]["max_volume"]) or
                      (sample_max_volumes[sample_detail.sample.name]["max_volume"] and
                       sample_detail.volume > sample_max_volumes[sample_detail.sample.name]["max_volume"]))):
                sample_max_volumes[sample_detail.sample.name] = {"id": sample_detail.id, "max_volume": sample_detail.volume}
        for sample_detail in sample_details:
            if sample_detail.id == sample_max_volumes[sample_detail.sample.name]['id']:
                collection_sample_objs.append(sample_detail)
        return collection_sample_objs

    class Meta:
        db_table = "partner_lab_test_sample_details"


class PartnerLabSamplesCollectOrder(auth_models.TimeStampedModel, auth_models.CreatedByModel):

    SAMPLE_EXTRACTION_PENDING = 1
    SAMPLE_SCAN_PENDING = 2
    SAMPLE_PICKUP_PENDING = 3
    SAMPLE_PICKED_UP = 4
    PARTIAL_REPORT_GENERATED = 5
    REPORT_GENERATED = 6
    REPORT_VIEWED = 7
    CANCELLED_BY_DOCTOR = 8
    CANCELLED_BY_LAB = 9
    STATUS_CHOICES = [(SAMPLE_EXTRACTION_PENDING, "Sample Extraction Pending"),
                      (SAMPLE_SCAN_PENDING, "Sample Scan Pending"),
                      (SAMPLE_PICKUP_PENDING, "Sample Pickup Pending"),
                      (SAMPLE_PICKED_UP, "Sample Picked Up"),
                      (PARTIAL_REPORT_GENERATED, "Partial Report Generated"),
                      (REPORT_GENERATED, "Report Generated"),
                      (REPORT_VIEWED, "Report Viewed"),
                      (CANCELLED_BY_DOCTOR, "Cancelled by Doctor"),
                      (CANCELLED_BY_LAB, "Cancelled by Lab")]

    id = models.BigAutoField(primary_key=True)
    offline_patient = models.ForeignKey(doc_models.OfflinePatients, on_delete=models.CASCADE, related_name="patient_lab_samples_collect_order")
    patient_details = JSONField()
    hospital = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE, related_name="hosp_lab_samples_collect_order")
    doctor = models.ForeignKey(doc_models.Doctor, on_delete=models.CASCADE, related_name="doc_lab_samples_collect_order")
    lab = models.ForeignKey(diag_models.Lab, on_delete=models.CASCADE, related_name="lab_samples_collect_order")
    available_lab_tests = models.ManyToManyField(diag_models.AvailableLabTest, related_name="tests_lab_samples_collect_order")
    collection_datetime = models.DateTimeField(null=True, blank=True)
    samples = JSONField()
    selected_tests_details = JSONField()
    lab_alerts = models.ManyToManyField(TestSamplesLabAlerts)
    status = models.SmallIntegerField(choices=STATUS_CHOICES)
    extras = JSONField(default={})

    def __str__(self):
        return str(self.offline_patient.name) + '-' + str(self.hospital.name)

    class Meta:
        db_table = "partner_lab_samples_collect_order"

    def status_update_checks(self, new_status):
        if not new_status:
            return {"is_correct": False, "message": "new status not found"}
        if self.status in [self.CANCELLED_BY_DOCTOR, self.CANCELLED_BY_LAB]:
            return {"is_correct": False, "message": "Status can't be updated once cancelled"}
        if new_status in [self.CANCELLED_BY_DOCTOR, self.CANCELLED_BY_LAB] \
                and self.status in [self.PARTIAL_REPORT_GENERATED, self.REPORT_GENERATED, self.REPORT_VIEWED]:
            return {"is_correct": False,
                    "message": "Order can't be cancelled if status is 'Partial Report Generated' or 'Report Generated' or 'Report Viewed'"}
        if new_status not in [self.CANCELLED_BY_DOCTOR, self.CANCELLED_BY_LAB] and self.status > new_status:
            return {"is_correct": False, "message": "Incorrect status update"}
        if self.status < self.SAMPLE_PICKED_UP and new_status in [self.REPORT_GENERATED, self.PARTIAL_REPORT_GENERATED]:
            return {"is_correct": False, "message": "Report can't be generated until sample is picked"}
        return {"is_correct": True, "message": ""}

    def save(self, *args, **kwargs):
        super(PartnerLabSamplesCollectOrder, self).save()
        if self.status == self.SAMPLE_PICKUP_PENDING:
            notification_tasks.send_partner_lab_notifications.apply_async(kwargs={'order_id': self.id,
                                                                                  'notification_type': NotificationAction.PARTNER_LAB_ORDER_PLACED_SUCCESSFULLY},
                                                                          countdown=3)


class PartnerLabTestSamplesOrderReportMapping(auth_models.TimeStampedModel):

    order = models.ForeignKey(PartnerLabSamplesCollectOrder, on_delete=models.CASCADE, related_name="reports")
    report = models.FileField(upload_to='provider/cloud-lab/reports', validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpeg', 'jpg', 'png'])])

    def __str__(self):
        return str(self.report)

    class Meta:
        db_table = 'partner_lab_test_sample_order_report_mapping'
