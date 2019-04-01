import datetime
from django.core.validators import FileExtensionValidator

from ondoc.notification.tasks import send_insurance_notifications
from ondoc.insurance.tasks import push_insurance_buy_to_matrix, push_insurance_banner_lead_to_matrix
import json

from django.db import models, transaction
from django.db.models import Q
import logging
from ondoc.authentication import models as auth_model
from ondoc.account import models as account_model
from django.core.validators import MaxValueValidator, MinValueValidator
from ondoc.authentication.models import UserProfile, User
from django.contrib.postgres.fields import JSONField
from django.forms import model_to_dict
from ondoc.common.helper import Choices
from django.core.files.uploadedfile import TemporaryUploadedFile
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from ondoc.api.v1.utils import RawSql, aware_time_zone
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.template.loader import render_to_string
from num2words import num2words
from hardcopy import bytestring_to_pdf
import math
from ondoc.account.models import Order
from decimal import  *
logger = logging.getLogger(__name__)


def generate_insurance_policy_number():
    query = '''select nextval('userinsurance_policy_num_seq') as inc'''
    seq = RawSql(query, []).fetch_all()
    sequence = None
    if seq:
        sequence = seq[0]['inc'] if seq[0]['inc'] else None

    if sequence:
        return str('120100/12001/2018/A012708/DP%.8d' % sequence)
    else:
        raise ValueError('Sequence Produced is not valid.')


def generate_insurance_reciept_number():
    query = '''select nextval('userinsurance_policy_reciept_seq') as inc'''
    seq = RawSql(query, []).fetch_all()
    sequence = None
    if seq:
        sequence = seq[0]['inc'] if seq[0]['inc'] else None

    if sequence:
        return int("1%.8d" % sequence)
    else:
        raise ValueError('Sequence Produced is not valid.')


class InsuranceGynocologist:
    def __init__(self):
        self.specializaion_ids = set(json.loads(settings.GYNECOLOGIST_SPECIALIZATION_IDS))

    def get_booked_appointments_count(self, user, insurance_id):
        from ondoc.doctor.models import DoctorPracticeSpecialization, OpdAppointment
        error = None
        count = 0

        doctor_with_gyno_specialization = DoctorPracticeSpecialization.objects. \
            filter(specialization_id__in=list(self.specializaion_ids)).values_list('doctor_id', flat=True)

        if doctor_with_gyno_specialization:
            count = OpdAppointment.objects.filter(~Q(status=OpdAppointment.CANCELLED),
                                                  doctor_id__in=doctor_with_gyno_specialization,
                                                  payment_type=OpdAppointment.INSURANCE,
                                                  insurance_id=insurance_id,
                                                  user=user).count()

        if count >= int(settings.INSURANCE_GYNECOLOGIST_LIMIT):
            error = "Gynocologist limit exceeded of limit 5"

        return count, error


class InsuranceOncologist:
    def __init__(self):
        self.specializaion_ids = set(json.loads(settings.ONCOLOGIST_SPECIALIZATION_IDS))

    def get_booked_appointments_count(self, user, insurance_id):
        from ondoc.doctor.models import DoctorPracticeSpecialization, OpdAppointment
        error = None
        count = 0

        doctor_with_onco_specialization = DoctorPracticeSpecialization.objects. \
            filter(specialization_id__in=list(self.specializaion_ids)).values_list('doctor_id', flat=True)

        if doctor_with_onco_specialization:
            count = OpdAppointment.objects.filter(~Q(status=OpdAppointment.CANCELLED),
                                                  doctor_id__in=doctor_with_onco_specialization,
                                                  payment_type=OpdAppointment.INSURANCE,
                                                  insurance_id=insurance_id,
                                                  user=user).count()
        if count >= int(settings.INSURANCE_ONCOLOGIST_LIMIT):
            error = "Oncologist limit exceeded of limit 5"

        return count, error


class InsuranceDoctorSpecializations(object):
    class SpecializationMapping:
        GYNOCOLOGIST = 'GYNOCOLOGIST'
        ONCOLOGIST = 'ONCOLOGIST'

        specialization_mapping = {
            'GYNOCOLOGIST': InsuranceGynocologist,
            'ONCOLOGIST': InsuranceOncologist
        }


    @classmethod
    def get_doctor_insurance_specializations(cls, doctor):
        from ondoc.doctor.models import DoctorPracticeSpecialization, OpdAppointment
        all_gynecologist_list = set(json.loads(settings.GYNECOLOGIST_SPECIALIZATION_IDS))
        all_oncologist_list = set(json.loads(settings.ONCOLOGIST_SPECIALIZATION_IDS))

        result = False
        specialization = None
        doctor_specialization_ids = DoctorPracticeSpecialization.objects.filter(doctor_id=doctor).values_list('specialization_id', flat=True)
        doctor_specialization_ids_set = set(doctor_specialization_ids)
        for specialiization_id in doctor_specialization_ids_set:
            if specialiization_id in all_gynecologist_list:
                # self.doctor_specialization = InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST
                result, specialization = True, cls.SpecializationMapping.GYNOCOLOGIST
                break
            elif specialiization_id in all_oncologist_list:
                # self.doctor_specialization = InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST
                result, specialization = True, cls.SpecializationMapping.ONCOLOGIST
                break
            else:
                result = False

        if not result or not specialization:
            return None

        return result, specialization

    @classmethod
    def get_already_booked_specialization_appointments(cls, user, insurance_id, **kwargs):
        if not user:
            return None
        specialization_count_dict = dict()

        asked_doctor_specialization = kwargs.get('doctor_specialization')

        if not asked_doctor_specialization:
            for specialization, class_ref in cls.SpecializationMapping.specialization_mapping.items():
                obj = class_ref()
                count, error = obj.get_booked_appointments_count(user, insurance_id)
                specialization_count_dict[specialization] = {'specialization': specialization, 'count': count, 'error': error}
        else:
            class_ref = cls.SpecializationMapping.specialization_mapping[asked_doctor_specialization]
            obj = class_ref()
            count, error = obj.get_booked_appointments_count(user, insurance_id)
            specialization_count_dict[asked_doctor_specialization] = {'specialization': asked_doctor_specialization, 'count': count, 'error': error}

        return specialization_count_dict


class LiveMixin(models.Model):
    def save(self, *args, **kwargs):
        if self.enabled:
            self.is_live = True
        else:
            self.is_live = False
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class StateGSTCode(auth_model.TimeStampedModel):
    gst_code = models.CharField(max_length=10)
    state_name = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    is_live = models.BooleanField(default=True)

    @property
    def get_active_city(self):
        return self.related_cities.filter(is_live=True).order_by('city_name')

    @property
    def get_active_district(self):
        return self.related_districts.filter(is_live=True).order_by('district_name')

    def __str__(self):
        return "{} ({})".format(self.gst_code, self.state_name)

    class Meta:
        db_table = "insurance_state"


class InsuranceCity(auth_model.TimeStampedModel):
    city_code = models.CharField(max_length=10)
    city_name = models.CharField(max_length=100)
    state = models.ForeignKey(StateGSTCode, related_name="related_cities", on_delete=models.SET_NULL, null=True)
    is_enabled = models.BooleanField(default=True)
    is_live = models.BooleanField(default=True)

    def __str__(self):
        return "{} ({})".format(self.city_code, self.city_name)

    class Meta:
        db_table = "insurance_city"


class InsuranceDistrict(auth_model.TimeStampedModel):
    district_code = models.CharField(max_length=10)
    district_name = models.CharField(max_length=100)
    state = models.ForeignKey(StateGSTCode, related_name="related_districts", on_delete=models.SET_NULL, null=True)
    is_enabled = models.BooleanField(default=True)
    is_live = models.BooleanField(default=True)

    def __str__(self):
        return "{} ({})".format(self.district_code, self.district_name)

    class Meta:
        db_table = "insurance_district"


class Insurer(auth_model.TimeStampedModel, LiveMixin):
    name = models.CharField(max_length=100)
    min_float = models.PositiveIntegerField(default=None)
    logo = models.ImageField('Insurer Logo', upload_to='insurer/images', null=True, blank=False)
    website = models.CharField(max_length=100, null=True, blank=False)
    phone_number = models.BigIntegerField(blank=False, null=True)
    email = models.EmailField(max_length=100, null=True, blank=False)
    address = models.CharField(max_length=500, null=True, blank=False, default='')
    company_name = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_name = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_code = models.CharField(max_length=100, null=True, blank=False, default='')
    intermediary_contact_number = models.BigIntegerField(blank=False, null=True)
    gstin_number = models.CharField(max_length=50, null=True, blank=False, default='')
    signature = models.ImageField('Insurer Signature', upload_to='insurer/images', null=True, blank=False)
    is_live = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    insurer_document = models.FileField(null=True,blank=False, upload_to='insurer/documents',
                                        validators=[FileExtensionValidator(allowed_extensions=['pdf'])])
    igst = models.PositiveSmallIntegerField(blank=False, null=True)
    sgst = models.PositiveSmallIntegerField(blank=False, null=True)
    cgst = models.PositiveSmallIntegerField(blank=False, null=True)
    state = models.ForeignKey(StateGSTCode, on_delete=models.CASCADE, default=None, blank=False, null=True)
    insurer_merchant_code = models.CharField(max_length=100, null=True, blank=False, unique=True)

    @property
    def get_active_plans(self):
        return self.plans.filter(is_live=True).order_by('total_allowed_members')

    def __str__(self):
        return self.name

    class Meta:
        db_table = "insurer"


class InsurerAccount(auth_model.TimeStampedModel):

    insurer = models.ForeignKey(Insurer, related_name="float", on_delete=models.CASCADE)
    current_float = models.PositiveIntegerField(default=None)

    def __str__(self):
        return str(self.insurer)

    class Meta:
        db_table = "insurer_account"


class InsurancePlans(auth_model.TimeStampedModel, LiveMixin):
    insurer = models.ForeignKey(Insurer,related_name="plans", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    amount = models.PositiveIntegerField(default=0)
    policy_tenure = models.PositiveIntegerField(default=1)
    adult_count = models.SmallIntegerField(default=0)
    child_count = models.SmallIntegerField(default=0)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)
    total_allowed_members = models.PositiveSmallIntegerField(default=0)
    is_selected = models.BooleanField(default=False)

    @property
    def get_active_threshold(self):
        return self.threshold.filter(is_live=True)

    def get_people_covered(self):
        return "%d adult, %d childs" % (self.adult_count, self.child_count)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "insurance_plans"


class InsurancePlanContent(auth_model.TimeStampedModel):

    class PossibleTitles(Choices):
        SALIENT_FEATURES = 'SALIENT_FEATURES'
        WHATS_NOT_COVERED = 'WHATS_NOT_COVERED'

    plan = models.ForeignKey(InsurancePlans,related_name="content", on_delete=models.CASCADE)
    title = models.CharField(max_length=500, blank=False, choices=PossibleTitles.as_choices())
    content = models.TextField(blank=False)

    class Meta:
        db_table = 'insurance_plan_content'


class InsuranceThreshold(auth_model.TimeStampedModel, LiveMixin):
    insurance_plan = models.ForeignKey(InsurancePlans, related_name="threshold", on_delete=models.CASCADE)
    opd_count_limit = models.PositiveIntegerField(default=0)
    opd_amount_limit = models.PositiveIntegerField(default=0)
    lab_count_limit = models.PositiveIntegerField(default=0)
    lab_amount_limit = models.PositiveIntegerField(default=0)
    min_age = models.PositiveIntegerField(default=0)
    max_age = models.PositiveIntegerField(default=0)
    child_min_age = models.PositiveIntegerField(default=0)
    child_max_age = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return str(self.insurance_plan)

    def age_validate(self, member):
        message = {}
        is_dob_valid = False
        # Calculate day difference between dob and current date
        # current_date = datetime.datetime.now().date()
        current_date = timezone.now().date()
        days_diff = current_date - member['dob']
        days_diff = days_diff.days
        years_diff = days_diff / 365
        years_diff = math.ceil(years_diff)
        adult_max_age = self.max_age
        adult_min_age = self.min_age
        child_min_age = self.child_min_age
        child_max_age = self.child_max_age
        # Age validation for parent in years
        if member['member_type'] == "adult":
            if (adult_max_age >= years_diff) and (adult_min_age <= years_diff):
                is_dob_valid = True
            elif adult_max_age <= years_diff:
                message = {"message": "Adult Age should be less than " + str(adult_max_age) + " years"}
            elif adult_min_age >= years_diff:
                message = {"message": "Adult Age should be more than " + str(adult_min_age) + " years"}
        # Age validation for child in days
        #TODO INSURANCE check max age
        if member['member_type'] == "child":
            if child_min_age <= days_diff and math.ceil(days_diff/365) <= child_max_age:
                is_dob_valid = True
            else:
                message = {"message": "Child Age should be more than " + str(child_min_age) + " days or less than" +
                                      str(child_max_age) + " years"}

        return is_dob_valid, message


    class Meta:
        db_table = "insurance_threshold"


class UserInsurance(auth_model.TimeStampedModel):
    from ondoc.account.models import MoneyPool

    insurance_plan = models.ForeignKey(InsurancePlans, related_name='active_users', on_delete=models.DO_NOTHING)
    user = models.ForeignKey(auth_model.User, related_name='purchased_insurance', on_delete=models.DO_NOTHING)
    purchase_date = models.DateTimeField(blank=False, null=False)
    expiry_date = models.DateTimeField(blank=False, null=False, default=timezone.now)
    policy_number = models.CharField(max_length=100, blank=False, null=False, unique=True, default=generate_insurance_policy_number)
    insured_members = JSONField(blank=False, null=False)
    premium_amount = models.PositiveIntegerField(default=0)
    order = models.ForeignKey(account_model.Order, on_delete=models.DO_NOTHING)
    receipt_number = models.BigIntegerField(null=False, unique=True, default=generate_insurance_reciept_number)
    coi = models.FileField(default=None, null=True, upload_to='insurance/coi', validators=[FileExtensionValidator(allowed_extensions=['pdf'])])
    price_data = JSONField(blank=True, null=True)
    money_pool = models.ForeignKey(MoneyPool, on_delete=models.SET_NULL, null=True)
    matrix_lead_id = models.IntegerField(null=True)

    def __str__(self):
        return str(self.user)

    def get_primary_member_profile(self):
        insured_members = self.members.filter().order_by('id')
        proposers = list(filter(lambda member: member.relation.lower() == 'self', insured_members))
        if proposers:
            return proposers[0]

        return None

    def generate_pdf(self):
        insurer_state_code_obj = self.insurance_plan.insurer.state
        insurer_state_code = insurer_state_code_obj.gst_code
        insured_members = self.members.filter().order_by('id')
        proposer = self.get_primary_member_profile()
        proposer_fname = proposer.first_name if proposer.first_name else ""
        proposer_mname = proposer.middle_name if proposer.middle_name else ""
        proposer_lname = proposer.last_name if proposer.last_name else ""
        gst_state_code = proposer.state_code

        proposer_name = proposer.get_full_name()

        member_list = list()
        count = 1
        for member in insured_members:
            # fname = member.first_name if member.first_name else ""
            # mname = member.middle_name if member.middle_name else ""
            # lname = member.last_name if member.last_name else ""

            name = member.get_full_name()
            data = {
                'name': name.title(),
                'member_number': count,
                'dob': member.dob.strftime('%d-%m-%Y'),
                'relation': member.relation.title(),
                'id': member.id,
                'gender': member.gender.title(),
                'age': int((datetime.datetime.now().date() - member.dob).days/365),
            }
            member_list.append(data)
            count = count + 1

        threshold = self.insurance_plan.threshold.filter().first()

        # Gst calculation.

        premium_amount = Decimal(self.premium_amount)
        amount_without_tax = (premium_amount * Decimal(100)) / Decimal(118)

        cgst_tax = 'NA'
        sgst_tax = 'NA'
        igst_tax = 'NA'
        total_tax = 'NA'

        if insurer_state_code == gst_state_code and self.insurance_plan.insurer.cgst and self.insurance_plan.insurer.sgst:
            cgst_tax_numeric = (amount_without_tax/Decimal(100)) * Decimal(self.insurance_plan.insurer.cgst)
            cgst_tax = '%.2f' % (float(str(cgst_tax_numeric)))

            sgst_tax_numeric = (amount_without_tax/Decimal(100)) * Decimal(self.insurance_plan.insurer.sgst)
            sgst_tax = '%.2f' % (float(str(sgst_tax_numeric)))

            total_tax = cgst_tax_numeric + sgst_tax_numeric
            total_tax = '%.2f' % (float(str(total_tax)))

        elif insurer_state_code != gst_state_code and self.insurance_plan.insurer.igst:
            igst_tax = (amount_without_tax/Decimal(100)) * Decimal(self.insurance_plan.insurer.igst)
            igst_tax = '%.2f' % (float(str(igst_tax)))
            total_tax = igst_tax

        context = {
            'total_tax': total_tax,
            'sgst_rate': '(%s%%)' % str(self.insurance_plan.insurer.sgst) if self.insurance_plan.insurer.sgst else '',
            'cgst_rate': '(%s%%)' % str(self.insurance_plan.insurer.cgst) if self.insurance_plan.insurer.cgst else '',
            'igst_rate': '(%s%%)' % str(self.insurance_plan.insurer.igst) if self.insurance_plan.insurer.igst else '',
            'net_premium': '%.2f' % float(str(amount_without_tax)),
            'cgst_rate_tax': cgst_tax,
            'sgst_rate_tax': sgst_tax,
            'igst_rate_tax': igst_tax,
            'gross_amount': self.premium_amount,
            'purchase_data': str(aware_time_zone(self.purchase_date).date().strftime('%d-%m-%Y')),
            'start_time': str(aware_time_zone(self.purchase_date).strftime('%H:%M')),
            'expiry_date': str(aware_time_zone(self.expiry_date).date().strftime('%d-%m-%Y')),
            'end_time': str(aware_time_zone(self.expiry_date).strftime('%H:%M')),
            'opd_amount_limit': threshold.opd_amount_limit,
            'lab_amount_limit': threshold.lab_amount_limit,
            'premium': self.premium_amount,
            'premium_in_words': ('%s rupees ' % num2words(self.premium_amount)).title() + "only",
            'proposer_name': proposer_name.title(),
            'proposer_address': '%s, %s, %s, %s, %d' % (proposer.address, proposer.town, proposer.district, proposer.state, proposer.pincode),
            'proposer_mobile': proposer.phone_number,
            'proposer_email': proposer.email,
            'intermediary_name': self.insurance_plan.insurer.intermediary_name,
            'intermediary_code': self.insurance_plan.insurer.intermediary_code,
            'intermediary_contact_number': self.insurance_plan.insurer.intermediary_contact_number,
            'issuing_office_address': self.insurance_plan.insurer.address,
            'issuing_office_gstin': self.insurance_plan.insurer.gstin_number,
            'group_policy_name': 'Docprime Technologies Pvt. Ltd.',
            'group_policy_address': 'Plot No. 119, Sector 44, Gurugram, Haryana 122001',
            'group_policy_email': 'customercare@docprime.com',
            'nominee_name': 'Legal heir',
            'nominee_relation': 'Legal heir',
            'nominee_address': 'Same as proposer',
            'policy_related_email_static': 'customercare@docprime.com',
            'policy_related_email': '%s' % self.insurance_plan.insurer.email,
            'policy_related_tollno_static': '18001239419',
            'policy_related_tollno': '%d' % self.insurance_plan.insurer.intermediary_contact_number,
            'policy_related_website_static': 'https://docprime.com',
            'policy_related_website': '%s' % self.insurance_plan.insurer.website,
            'current_date': timezone.now().date().strftime('%d-%m-%Y'),
            'policy_number': self.policy_number,
            'application_number': self.id,
            'total_member_covered': len(member_list),
            'plan': self.insurance_plan.name,
            'insured_members': member_list,
            'insurer_logo': self.insurance_plan.insurer.logo.url,
            'insurer_signature': self.insurance_plan.insurer.signature.url,
            'company_name': self.insurance_plan.insurer.company_name,
            'insurer_name': self.insurance_plan.insurer.name,
            'gst_state_code': gst_state_code,
            'reciept_number': self.receipt_number
        }
        html_body = render_to_string("pdfbody.html", context=context)
        policy_number = self.policy_number
        certificate_number = policy_number.split('/')[-1]
        filename = "{}.pdf".format(str(certificate_number))
        try:
            extra_args = {
                'virtual-time-budget': 6000
            }
            file = TemporaryUploadedFile(filename, 'byte', 1000, 'utf-8')
            f = open(file.temporary_file_path())
            bytestring_to_pdf(html_body.encode(), f, **extra_args)
            f.seek(0)
            f.flush()
            f.content_type = 'application/pdf'

            self.coi = InMemoryUploadedFile(file, None, filename, 'application/pdf', file.tell(), None)
            self.save()
        except Exception as e:
            logger.error("Got error while creating pdf for opd invoice {}".format(e))

    class Meta:
        db_table = "user_insurance"

    def is_valid(self):
        if self.expiry_date >= timezone.now():
            return True
        else:
            return False

    def is_appointment_valid(self, appointment_time):
        if self.expiry_date >= appointment_time:
            return True
        else:
            return False

    def doctor_specialization_validation(self, appointment_data):
        from ondoc.doctor.models import DoctorPracticeSpecialization, OpdAppointment
        profile = appointment_data['profile']
        doctor = DoctorPracticeSpecialization.objects.filter(doctor_id=appointment_data['doctor']).values(
            'specialization_id')
        specilization_ids = doctor
        specilization_ids_set = set(map(lambda specialization: specialization['specialization_id'], specilization_ids))
        gynecologist_list = json.loads(settings.GYNECOLOGIST_SPECIALIZATION_IDS)
        gynecologist_set = set(gynecologist_list)
        oncologist_list = json.loads(settings.ONCOLOGIST_SPECIALIZATION_IDS)
        oncologist_set = set(oncologist_list)
        if not (specilization_ids_set & oncologist_set) and not (specilization_ids_set & gynecologist_set):
            return True, self.id, 'Covered Under Insurance'
        members = self.members.all().get(profile=profile)
        if specilization_ids_set & gynecologist_set:
            doctor_with_same_specialization = DoctorPracticeSpecialization.objects.filter(
                specialization_id__in=gynecologist_list).values_list(
                'doctor_id', flat=True)
            gynecologist_opd_count = OpdAppointment.objects.filter(~Q(status=6),
                                                                  doctor_id__in=doctor_with_same_specialization,
                                                                  payment_type=3,
                                                                  insurance_id=self.id,
                                                                  profile_id=members.profile.id).count()
            if gynecologist_opd_count > int(settings.INSURANCE_GYNECOLOGIST_LIMIT):
                return False, self.id, 'Gynecologist Limit of 5 exceeded'
            else:
                return True, self.id, 'Covered Under Insurance'
        elif specilization_ids_set & oncologist_set:
            doctor_with_same_specialization = DoctorPracticeSpecialization.objects.filter(
                specialization_id__in=oncologist_list).values_list(
                'doctor_id', flat=True)
            oncologist_opd_count = OpdAppointment.objects.filter(~Q(status=6),
                                                                  doctor_id__in=doctor_with_same_specialization,
                                                                  payment_type=3,
                                                                  insurance_id=self.id,
                                                                  profile_id=members.profile.id).count()
            if oncologist_opd_count > int(settings.INSURANCE_ONCOLOGIST_LIMIT):
                return False, self.id, 'Oncologist Limit of 5 exceeded'
            else:
                return True, self.id, 'Covered Under Insurance'

    def get_doctor_specialization_count(self, appointment_data):
        from ondoc.doctor.models import DoctorPracticeSpecialization, OpdAppointment
        gynecologist_opd_count = 0
        oncologist_opd_count = 0
        profile = appointment_data['profile']
        if not profile:
            return gynecologist_opd_count, oncologist_opd_count
        user = profile.user
        doctor = DoctorPracticeSpecialization.objects.filter(doctor_id=appointment_data['doctor']).values(
            'specialization_id')
        specilization_ids = doctor
        specilization_ids_set = set(
            map(lambda specialization: specialization['specialization_id'], specilization_ids))
        gynecologist_list = json.loads(settings.GYNECOLOGIST_SPECIALIZATION_IDS)
        gynecologist_set = set(gynecologist_list)
        oncologist_list = json.loads(settings.ONCOLOGIST_SPECIALIZATION_IDS)
        oncologist_set = set(oncologist_list)
        if not (specilization_ids_set & oncologist_set) and not (specilization_ids_set & gynecologist_set):
            return gynecologist_opd_count, oncologist_opd_count

        # members = self.members.all().get(profile=profile)
        # if specilization_ids_set & gynecologist_set:
        doctor_with_gyno_specialization = DoctorPracticeSpecialization.objects.filter(
            specialization_id__in=gynecologist_list).values_list(
            'doctor_id', flat=True)
        if doctor_with_gyno_specialization:
            # gynecologist_opd_count = OpdAppointment.objects.filter(~Q(status=6),
            #                                                    doctor_id__in=doctor_with_gyno_specialization,
            #                                                    payment_type=3,
            #                                                    insurance_id=self.id,
            #                                                    profile_id=members.profile.id).count()
            gynecologist_opd_count = OpdAppointment.objects.filter(~Q(status=OpdAppointment.CANCELLED),
                                                                   doctor_id__in=doctor_with_gyno_specialization,
                                                                   payment_type=OpdAppointment.INSURANCE,
                                                                   insurance_id=self.id,
                                                                   user=user).count()
        # elif specilization_ids_set & oncologist_set:
        doctor_with_onco_specialization = DoctorPracticeSpecialization.objects.filter(
            specialization_id__in=oncologist_list).values_list(
            'doctor_id', flat=True)
        if doctor_with_onco_specialization:
            # oncologist_opd_count = OpdAppointment.objects.filter(~Q(status=6),
            #                                                  doctor_id__in=doctor_with_onco_specialization,
            #                                                  payment_type=3,
            #                                                  insurance_id=self.id,
            #                                                  profile_id=members.profile.id).count()
            oncologist_opd_count = OpdAppointment.objects.filter(~Q(status=OpdAppointment.CANCELLED),
                                                             doctor_id__in=doctor_with_onco_specialization,
                                                             payment_type=OpdAppointment.INSURANCE,
                                                             insurance_id=self.id,
                                                             user=user).count()

        return gynecologist_opd_count, oncologist_opd_count

    # TODO Incase if Lab limit has to apply on monthly basis.
    # def is_lab_appointment_count_valid(self, appointment_data):
    #     from ondoc.diagnostic.models import LabAppointment
    #     start_time = appointment_data['time_slot_start'] - timedelta(days=30)
    #     end_time = appointment_data['time_slot_start']
    #     threshold = self.insurance_plan.threshold.filter().first()
    #     lab_appointment_count = LabAppointment.objects.filter(~Q(status=6), lab=appointment_data['lab'],
    #                                                           time_slot_start__range=(start_time, end_time),
    #                                                           user_id=self.user_id, payment_type=3,
    #                                                           insurance_id=self.id).count()
    #     if lab_appointment_count >= threshold.lab_count_limit:
    #         return False
    #     else:
    #         return True
    # TODO Incase if Opd limit has to apply on monthly basis.
    # def is_opd_appointment_count_valid(self, appointment_data):
    #     from ondoc.doctor.models import OpdAppointment
    #     start_time = appointment_data['time_slot_start'] - timedelta(days=30)
    #     end_time = appointment_data['time_slot_start']
    #     threshold = self.insurance_plan.threshold.filter().first()
    #     opd_appointment_count = OpdAppointment.objects.filter(~Q(status=6), doctor=appointment_data['doctor'],
    #                                                           time_slot_start__range=(start_time, end_time),
    #                                                           user_id=self.user_id, payment_type=3,
    #                                                           insurance_id=self.id).count()
    #     if opd_appointment_count >= threshold.opd_count_limit:
    #         return False
    #     else:
    #         return True



    @classmethod
    def profile_create_or_update(cls, member, user):
        profile = {}
        name = "{fname} {mname} {lname}".format(fname=member['first_name'], mname=member['middle_name'],
                                                lname=member['last_name'])
        if member['profile'] or UserProfile.objects.filter(name__iexact=name, user=user.id).exists():
            # Check whether Profile exist with same name
            existing_profile = UserProfile.objects.filter(name__iexact=name, user=user.id).first()
            if member['profile']:
                profile = member['profile']
            elif existing_profile:
                profile = existing_profile
            if profile:
                if profile.user_id == user.id:
                    profile.name = name
                    profile.email = member['email']
                    profile.gender = member['gender']
                    profile.dob = member['dob']
                    profile.save()

                profile = profile.id
        # Create Profile if not exist with name or not exist in profile id from request
        else:
            # primary_user = UserProfile.objects.filter(user_id=user.id, is_default_user=True).first()
            data = {'name': name, 'email': member['email'], 'gender': member['gender'], 'user_id': user.id,
                    'dob': member['dob'], 'is_default_user': False, 'is_otp_verified': False,
                    'phone_number': user.phone_number}
            # if (primary_user or member['relation'] == 'self') and not default_user_profile:
            #     data['is_default_user'] = True
            #
            # member_profile = UserProfile.objects.create(**data)
            # profile = member_profile.id
            # default_user_profile.append(member_profile.id)
            if member['relation'] == 'self':
                data['is_default_user'] = True

            member_profile = UserProfile.objects.create(**data)
            profile = member_profile.id
            # default_user_profile.append(member_profile.id)

        return profile

    @classmethod
    def create_user_insurance(cls, insurance_data, user):
        members = insurance_data['insured_members']
        # default_user_profile = list()
        for member in members:
            member['profile'] = UserInsurance.profile_create_or_update(member, user)
            member['dob'] = str(member['dob'])
            # member['profile'] = member['profile'].id if member.get('profile') else None
        insurance_data['insured_members'] = members
        user_insurance_obj = UserInsurance.objects.create(insurance_plan=insurance_data['insurance_plan'],
                                                            user=insurance_data['user'],
                                                            insured_members=json.dumps(insurance_data['insured_members']),
                                                            purchase_date=insurance_data['purchase_date'],
                                                            expiry_date=insurance_data['expiry_date'],
                                                            premium_amount=insurance_data['premium_amount'],
                                                            order=insurance_data['order'])
        insured_members = InsuredMembers.create_insured_members(user_insurance_obj)
        return user_insurance_obj

    def validate_insurance(self, appointment_data):
        response_dict = {
            'is_insured': False,
            'insurance_id': None,
            'insurance_message': "",
            'doctor_specialization_dict': dict()
        }

        profile = appointment_data.get('profile', None)
        user = profile.user
        user_insurance = UserInsurance.objects.filter(user=user).last()
        if not user_insurance or not user_insurance.is_valid() or \
                not user_insurance.is_appointment_valid(appointment_data['start_date']):
            response_dict['insurance_message'] = 'Not covered under insurance'
            return response_dict
        else:
            response_dict['insurance_id'] = user_insurance.id

        insured_members = user_insurance.members.all().filter(profile=profile)
        if not insured_members.exists():
            response_dict['insurance_message'] = 'Profile Not covered under insurance'
            return response_dict

        threshold = InsuranceThreshold.objects.filter(insurance_plan_id=user_insurance.insurance_plan_id).first()
        if not threshold:
            response_dict['insurance_message'] = 'Threshold Amount Not define for plan'
            return response_dict

        if not 'doctor' in appointment_data:
            is_insured, insurance_id, insurance_message = user_insurance.validate_lab_insurance(appointment_data, user_insurance)
            response_dict['is_insured'] = is_insured
            response_dict['insurance_message'] = insurance_message

        else:
            is_insured, insurance_id, insurance_message = user_insurance.validate_doctor_insurance(appointment_data, user_insurance)
            response_dict['is_insured'] = is_insured
            response_dict['insurance_message'] = insurance_message

            doctor = appointment_data['doctor']
            if is_insured:
                if InsuranceDoctorSpecializations.get_doctor_insurance_specializations(doctor):
                    specialization_count_dict = InsuranceDoctorSpecializations.get_already_booked_specialization_appointments(
                        user, user_insurance.id)
                    response_dict['doctor_specialization_dict'] = specialization_count_dict

                    response_dict['is_insured'] = True
                    response_dict['insurance_id'] = user_insurance.id
                    response_dict['insurance_message'] = ""

                    if specialization_count_dict.get(InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST, {}) \
                            .get('count', 0) >= int(settings.INSURANCE_GYNECOLOGIST_LIMIT):
                        response_dict['is_insured'] = False
                        response_dict['insurance_id'] = None
                        response_dict['insurance_message'] = "Gynocologist Appointment exceeded of limit %d" % int(settings.INSURANCE_GYNECOLOGIST_LIMIT)

                    if specialization_count_dict.get(InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST, {}) \
                            .get('count', 0) >= int(settings.INSURANCE_ONCOLOGIST_LIMIT):
                        response_dict['is_insured'] = False
                        response_dict['insurance_id'] = None
                        response_dict['insurance_message'] = "Oncologist Appointment exceeded of limit 5"

                else:
                    response_dict['is_insured'] = True
                    response_dict['insurance_id'] = user_insurance.id
                    response_dict['insurance_message'] = ""
            else:
                response_dict['is_insured'] = False
                response_dict['insurance_id'] = None
                response_dict['insurance_message'] = ""

        return response_dict

    def validate_lab_insurance(self, appointment_data, user_insurance):
        from ondoc.diagnostic.models import AvailableLabTest
        lab = appointment_data['lab']
        lab_mrp_check_list = []
        if not lab.is_insurance_enabled:
            return False, None, 'Lab is not covered under insurance'
        threshold = InsuranceThreshold.objects.filter(insurance_plan_id=user_insurance.insurance_plan_id).first()
        threshold_lab = threshold.lab_amount_limit
        if appointment_data['test_ids']:
            for test in appointment_data['test_ids']:
                lab_test = AvailableLabTest.objects.filter(lab_pricing_group__labs=appointment_data["lab"],
                                                           test=test, enabled=True).first()
                if not lab_test:
                    return False, user_insurance.id, 'Price not available for Test'
                mrp = lab_test.mrp
                if mrp <= threshold_lab:
                    is_lab_insured = True
                else:
                    is_lab_insured = False
                lab_mrp_check_list.append(is_lab_insured)
            if not False in lab_mrp_check_list:
                return True, user_insurance.id, ''
            else:
                return False, None, ''
        else:
            return False, None, ''

    def validate_doctor_insurance(self, appointment_data, user_insurance):
        is_insured = True
        insurance_id = user_insurance.id
        insurance_message = ""
        from ondoc.doctor.models import OpdAppointment
        threshold = InsuranceThreshold.objects.filter(insurance_plan_id=user_insurance.insurance_plan_id).first()
        threshold_opd = threshold.opd_amount_limit
        # profile = appointment_data.get('profile', None)
        # user = profile.user
        if appointment_data.get('procedure_ids', None):
            for detail in appointment_data:
                if detail['procedure_id']:
                    is_insured = False
                    insurance_id = None
                    insurance_message = "Procedure Not covered under insurance"
        doctor = appointment_data['doctor']
        if not doctor.is_insurance_enabled:
            is_insured = False
            insurance_id = None
            insurance_message = ""
        price_data = OpdAppointment.get_price_details(appointment_data)
        if not int(price_data.get('mrp')) <= threshold_opd:
            is_insured = False
            insurance_id = None
            insurance_message = ""
        return is_insured, insurance_id, insurance_message

    def is_doctor_gynecologist(self, doctor):
        from ondoc.doctor.models import DoctorPracticeSpecialization
        all_gynecologist_list = json.loads(settings.GYNECOLOGIST_SPECIALIZATION_IDS)
        result = False
        doctor_specialization_ids = DoctorPracticeSpecialization.objects.filter(doctor_id=doctor).values_list('specialization_id', flat=True)
        for specialiization_id in doctor_specialization_ids:
            if specialiization_id in all_gynecologist_list:
                result = True
                break
            else:
                result = False
        return result

    def is_doctor_oncologist(self, doctor):
        from ondoc.doctor.models import DoctorPracticeSpecialization
        all_oncologist_list = json.loads(settings.ONCOLOGIST_SPECIALIZATION_IDS)
        result = False
        doctor_specialization_ids = DoctorPracticeSpecialization.objects.filter(doctor_id=doctor).values_list('specialization_id', flat=True)
        for specialiization_id in doctor_specialization_ids:
            if specialiization_id in all_oncologist_list:
                result = True
                break
            else:
                result = False
        return result

    def validate_insurance_for_cart(self, appointment_data, cart_items):
        insurance_validate_dict = self.validate_insurance(appointment_data)
        is_insured = insurance_validate_dict['is_insured']
        insurance_id = insurance_validate_dict['insurance_id']
        insurance_message = insurance_validate_dict['insurance_message']

        gyno_count = 0
        onco_count = 0
        doctor = appointment_data.get('doctor', None)
        user = appointment_data.get('profile').user
        if not is_insured or not doctor:
            return is_insured, insurance_id, insurance_message

        specialization_result = InsuranceDoctorSpecializations.get_doctor_insurance_specializations(doctor)
        if specialization_result is None:
            return is_insured, insurance_id, insurance_message

        specialization_count_dict = insurance_validate_dict['doctor_specialization_dict']
        gyno_count = specialization_count_dict[InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST].get('count', 0)
        onco_count = specialization_count_dict[InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST].get('count', 0)

        if not specialization_count_dict:
            return is_insured, insurance_id, insurance_message
        if not cart_items:
            return is_insured, insurance_id, insurance_message

        for cart_item in cart_items:
            if cart_item.product_id == Order.DOCTOR_PRODUCT_ID:
                data = cart_item.data

                doctor_in_cart = data.get('doctor')
                doctor_specilization_tuple = InsuranceDoctorSpecializations.get_doctor_insurance_specializations(doctor_in_cart)
                if doctor_specilization_tuple is None:
                    return is_insured, insurance_id, insurance_message

                res, specialization = doctor_specilization_tuple[0], doctor_specilization_tuple[1]
                if specialization == InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST and data.get('is_appointment_insured'):
                    gyno_count = gyno_count + 1
                if specialization == InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST and data.get('is_appointment_insured'):
                    onco_count = onco_count + 1

                if gyno_count >= int(settings.INSURANCE_GYNECOLOGIST_LIMIT) and specialization == InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST:
                    return False, self.id, "Gynocologist limit exceeded of limit 5"
                if onco_count >= int(settings.INSURANCE_ONCOLOGIST_LIMIT) and specialization == InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST:
                    return False, self.id, "Oncologist limit exceeded of limit 5"
            else:
                return is_insured, insurance_id, insurance_message

        return is_insured, insurance_id, insurance_message

    @classmethod
    def validate_cart_items(cls,cart_items, request):
        from ondoc.doctor.models import OpdAppointment

        gyno_count = 0
        onco_count = 0
        user = request.user
        res_dict = dict()
        is_process = True
        error = ""
        user_insurance = UserInsurance.objects.filter(user=user).last()
        specialization_count_dict = None
        if user_insurance and user_insurance.is_valid():
            specialization_count_dict = InsuranceDoctorSpecializations.get_already_booked_specialization_appointments(
                user, user_insurance.id)
            gyno_count = specialization_count_dict.get(
                InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST, {}).get('count', 0)
            onco_count = specialization_count_dict.get(InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST,
                                                       {}).get('count', 0)
        else:
            is_process = True
        for item in cart_items:
            validated_data = item.validate(request)
            insurance_doctor = validated_data.get('doctor', None)
            insurance_lab = validated_data.get('lab', None)
            cart_data = validated_data.get('cart_item')
            cart_data = cart_data.data
            if cart_data.get('is_appointment_insured'):
                if insurance_doctor:
                    if user_insurance and user_insurance.is_valid() and specialization_count_dict:
                        doctor_specilization_tuple = InsuranceDoctorSpecializations.get_doctor_insurance_specializations(
                            insurance_doctor)
                        if doctor_specilization_tuple:
                            res, specialization = doctor_specilization_tuple[0], doctor_specilization_tuple[1]

                            if specialization == InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST and item.data.get(
                                    'is_appointment_insured'):
                                gyno_count = gyno_count + 1
                            if specialization == InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST and item.data.get(
                                    'is_appointment_insured'):
                                onco_count = onco_count + 1

                            if gyno_count > int(
                                    settings.INSURANCE_GYNECOLOGIST_LIMIT) and specialization == InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST:
                                is_process = False
                                error = "Gynecology limit exceeded"
                            if onco_count > int(
                                    settings.INSURANCE_ONCOLOGIST_LIMIT) and specialization == InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST:
                                is_process = False
                                error = "Oncology limit exceeded"
                        else:
                            is_process = True
                    else:
                        is_process = False
                elif insurance_lab:
                    is_insured, insurance_id, insurance_message = user_insurance.validate_lab_insurance(validated_data, user_insurance)
                    if is_insured:
                        is_process = True
                    else:
                        is_process = False
                        error = insurance_message
            else:
                is_process = True
        return is_process, error

    def trigger_created_event(self, visitor_info):
        from ondoc.tracking.models import TrackingEvent
        try:
            with transaction.atomic():
                event_data = TrackingEvent.build_event_data(self.user, TrackingEvent.InsurancePurchased, appointmentId=self.id)
                if event_data and visitor_info:
                    TrackingEvent.save_event(event_name=event_data.get('event'), data=event_data, visit_id=visitor_info.get('visit_id'),
                                             user=self.user, triggered_at=datetime.datetime.utcnow())
        except Exception as e:
            logger.error("Could not save triggered event - " + str(e))


class InsuranceTransaction(auth_model.TimeStampedModel):
    CREDIT = 1
    DEBIT = 2
    TRANSACTION_TYPE_CHOICES = ((CREDIT, 'CREDIT'), (DEBIT, "DEBIT"),)

    user_insurance = models.ForeignKey(UserInsurance,related_name='transactions', on_delete=models.DO_NOTHING)
    account = models.ForeignKey(InsurerAccount,related_name='transactions', on_delete=models.DO_NOTHING)
    transaction_type = models.PositiveSmallIntegerField(choices=TRANSACTION_TYPE_CHOICES)
    amount = models.PositiveSmallIntegerField(default=0)

    def after_commit_tasks(self):
        if self.transaction_type == InsuranceTransaction.DEBIT:
            # self.user_insurance.generate_pdf()
            # send_insurance_notifications(self.user_insurance.user.id)

            send_insurance_notifications.apply_async(({'user_id': self.user_insurance.user.id}, ),
                                                     link=push_insurance_buy_to_matrix.s(user_id=self.user_insurance.user.id), countdown=10)

    def save(self, *args, **kwargs):
        if self.pk:
            return

        super().save(*args, **kwargs)
        transaction_amount = self.amount
        if self.transaction_type == self.DEBIT:
            self.amount = -1*transaction_amount

        self.account.current_float += self.amount
        self.account.save()

        transaction.on_commit(lambda: self.after_commit_tasks())

    class Meta:
        db_table = "insurance_transaction"
        unique_together = (("user_insurance", "account", "transaction_type"),)


class InsuredMembers(auth_model.TimeStampedModel):
    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    GENDER_CHOICES = [(MALE, 'Male'), (FEMALE, 'Female'), (OTHER, 'Other')]
    SELF = 'self'
    SPOUSE = 'spouse'
    SON = 'son'
    DAUGHTER = 'daughter'
    RELATION_CHOICES = [(SPOUSE, 'Spouse'), (SON, 'Son'), (DAUGHTER, 'Daughter'), (SELF, 'Self')]
    ADULT = "adult"
    CHILD = "child"
    MEMBER_TYPE_CHOICES = [(ADULT, 'adult'), (CHILD, 'child')]
    MR = 'mr.'
    MISS = 'miss'
    MRS = 'mrs.'
    TITLE_TYPE_CHOICES = [(MR, 'mr.'), (MRS, 'mrs.'), (MISS, 'miss')]
    # insurer = models.ForeignKey(Insurer, on_delete=models.DO_NOTHING)
    # insurance_plan = models.ForeignKey(InsurancePlans, on_delete=models.DO_NOTHING)
    first_name = models.CharField(max_length=50, null=False)
    last_name = models.CharField(max_length=50, null=True)
    dob = models.DateField(blank=False, null=False)
    email = models.EmailField(max_length=100, null=True)
    relation = models.CharField(max_length=50, choices=RELATION_CHOICES, default=None)
    pincode = models.PositiveIntegerField(default=None)
    address = models.TextField(default=None)
    gender = models.CharField(max_length=50, choices=GENDER_CHOICES, default=None)
    phone_number = models.BigIntegerField(blank=True, null=True,
                                          validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    profile = models.ForeignKey(auth_model.UserProfile, related_name="insurance", on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=20, choices=TITLE_TYPE_CHOICES, default=None)
    middle_name = models.CharField(max_length=50, null=True)
    town = models.CharField(max_length=100, null=False)
    district = models.CharField(max_length=100, null=False)
    state = models.CharField(max_length=100, null=False)
    state_code = models.CharField(max_length=10, null=True)
    user_insurance = models.ForeignKey(UserInsurance, related_name="members", on_delete=models.DO_NOTHING, null=False)

    class Meta:
        db_table = "insured_members"

    def get_full_name(self):

        proposer_fname = self.first_name if self.first_name else ""
        proposer_mname = self.middle_name if self.middle_name else ""
        proposer_lname = self.last_name if self.last_name else ""

        proposer_name = '%s %s %s %s' % (self.title, proposer_fname, proposer_mname, proposer_lname)
        proposer_name = " ".join(proposer_name.split())
        return proposer_name

    @classmethod
    def create_insured_members(cls, user_insurance):
        import json
        members = user_insurance.insured_members
        members = json.loads(members)
        for member in members:
            user_profile = UserProfile.objects.get(id=member.get('profile'))
            insured_members_obj = InsuredMembers.objects.create(first_name=member.get('first_name'),
                                                                        title=member.get('title'),
                                                                        middle_name=member.get('middle_name'),
                                                                        last_name=member.get('last_name'),
                                                                        dob=member.get('dob'), email=member.get('email'),
                                                                        relation=member.get('relation'),
                                                                        address=member.get('address'),
                                                                        pincode=member.get('pincode'),
                                                                        phone_number=user_profile.phone_number,
                                                                        gender=member.get('gender'),
                                                                        profile=user_profile,
                                                                        town=member.get('town'),
                                                                        district=member.get('district'),
                                                                        state=member.get('state'),
                                                                        state_code = member.get('state_code'),
                                                                        user_insurance=user_insurance
                                                                        )


class Insurance(auth_model.TimeStampedModel):
    insurer = models.ForeignKey(Insurer, on_delete=models.SET_NULL, null=True)
    product_id = models.PositiveSmallIntegerField(choices=account_model.Order.PRODUCT_IDS)
    name = models.CharField(max_length=100)
    insurance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    insured_amount = models.DecimalField(max_digits=10, decimal_places=2)
    max_profile = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        db_table = "insurance"


class InsuranceDisease(auth_model.TimeStampedModel):
    disease = models.CharField(max_length=100)
    enabled = models.BooleanField()
    is_live = models.BooleanField()

    class Meta:
        db_table = "insurance_disease"


class InsuranceDiseaseResponse(auth_model.TimeStampedModel):
    disease = models.ForeignKey(InsuranceDisease, related_name="affected_members", on_delete=models.SET_NULL, null=True)
    member = models.ForeignKey(InsuredMembers, related_name="diseases", on_delete=models.SET_NULL, null=True)
    response = models.BooleanField(default=False)

    class Meta:
        db_table = "insurance_disease_response"


class InsuranceLead(auth_model.TimeStampedModel):
    matrix_lead_id = models.IntegerField(null=True)
    extras = JSONField(default={})
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        push_insurance_banner_lead_to_matrix.apply_async(({'id': self.id}, ), countdown=10)

    class Meta:
        db_table = 'insurance_leads'


