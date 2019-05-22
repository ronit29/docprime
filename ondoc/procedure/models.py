from django.contrib.postgres.fields import JSONField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from ondoc.authentication import models as auth_model
from ondoc.authentication.models import User, UserProfile
from ondoc.common.models import Feature, AppointmentHistory
from ondoc.doctor.models import DoctorClinic, SearchKey, Hospital, PracticeSpecialization, HealthInsuranceProvider
from collections import deque, OrderedDict

from ondoc.insurance.models import ThirdPartyAdministrator


class IpdProcedure(auth_model.TimeStampedModel, SearchKey, auth_model.SoftDelete):
    name = models.CharField(max_length=500, unique=True)
    synonyms = models.CharField(max_length=4000, null=True, blank=True)
    about = models.TextField(blank=True, verbose_name="Short description")
    details = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    features = models.ManyToManyField(Feature, through='IpdProcedureFeatureMapping',
                                      through_fields=('ipd_procedure', 'feature'), related_name='of_ipd_procedures')
    show_about = models.BooleanField(default=False)

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        db_table = "ipd_procedure"

    @classmethod
    def update_ipd_seo_urls(cls):
        from ondoc.location.services.doctor_urls import IpdProcedureSeo
        ipd_procedure = IpdProcedureSeo()
        ipd_procedure.create()


class IpdProcedurePracticeSpecialization(auth_model.TimeStampedModel):
    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE)
    practice_specialization = models.ForeignKey(PracticeSpecialization, on_delete=models.CASCADE)

    class Meta:
        db_table = "ipd_procedure_practice_specialization"
        unique_together = (('ipd_procedure', 'practice_specialization'),)


class IpdProcedureFeatureMapping(models.Model):
    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE,
                                      related_name='feature_mappings')
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE,
                                related_name='ipd_procedures_mappings')
    value = models.CharField(max_length=500, default='', blank=True)

    def __str__(self):
        return '{} - {}'.format(self.ipd_procedure.name, self.feature.name)

    class Meta:
        db_table = "ipd_procedure_feature_mapping"
        unique_together = (('ipd_procedure', 'feature'),)


class DoctorClinicIpdProcedure(auth_model.TimeStampedModel):
    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE, related_name="doctor_clinic_ipd_mappings")
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE, related_name="ipd_procedure_clinic_mappings")
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return '{} in {}'.format(str(self.ipd_procedure), str(self.doctor_clinic))

    class Meta:
        db_table = "doctor_clinic_ipd_procedure"
        unique_together = ('ipd_procedure', 'doctor_clinic')


class IpdProcedureCategory(auth_model.TimeStampedModel, SearchKey):
    name = models.CharField(max_length=500)

    def __str__(self):
        return self.name


class IpdProcedureCategoryMapping(models.Model):
    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE,
                                      related_name='ipd_category_mappings')
    category = models.ForeignKey(IpdProcedureCategory, on_delete=models.CASCADE,
                                 related_name='ipd_procedures_mappings')

    def __str__(self):
        return '{} - {}'.format(self.ipd_procedure.name, self.category.name)

    class Meta:
        db_table = "ipd_procedure_category_mapping"
        unique_together = (('ipd_procedure', 'category'),)


class IpdProcedureLead(auth_model.TimeStampedModel):

    NEW = 1
    COST_REQUESTED = 2
    COST_SHARED = 3
    OPD = 4
    NOT_INTERESTED = 5
    COMPLETED = 6

    CASH = 1
    INSURANCE = 2
    GOVERNMENT_PANEL = 3

    DOCPRIMECHAT = 'docprimechat'
    CRM = 'crm'
    DOCPRIMEWEB = "docprimeweb"

    SOURCE_CHOICES = [(DOCPRIMECHAT, 'DocPrime Chat'),
                      (CRM, 'CRM'),
                      (DOCPRIMEWEB, "DocPrime Web")]


    STATUS_CHOICES = [(None, "--Select--"), (NEW, 'NEW'), (COST_REQUESTED, 'COST_REQUESTED'),
                      (COST_SHARED, 'COST_SHARED'), (OPD, 'OPD'),
                      (NOT_INTERESTED, 'NOT_INTERESTED'), (COMPLETED, 'COMPLETED')]

    PAYMENT_TYPE_CHOICES = [(None, "--Select--"), (CASH, 'CASH'), (INSURANCE, 'INSURANCE'),
                            (GOVERNMENT_PANEL, 'GOVERNMENT_PANEL')]

    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.SET_NULL, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100, blank=False, null=True, default=None)
    phone_number = models.BigIntegerField(blank=True, null=True,
                                          validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    email = models.CharField(max_length=256, blank=True, null=True, default=None)
    gender = models.CharField(max_length=2, default=None, blank=True, null=True, choices=UserProfile.GENDER_CHOICES)
    age = models.PositiveIntegerField(blank=True, null=True)
    dob = models.DateTimeField(blank=True, null=True)
    lat = models.FloatField(null=True, default=None, blank=True)
    long = models.FloatField(null=True, default=None, blank=True)
    city = models.CharField(null=True, default=None, blank=True, max_length=150)
    source = models.CharField(max_length=256, blank=True, null=True, default=None,
                              choices=SOURCE_CHOICES)
    specialty = models.CharField(max_length=256, blank=True, null=True, default=None)
    matrix_lead_id = models.BigIntegerField(blank=True, null=True, unique=True)
    alternate_number = models.BigIntegerField(blank=True, null=True,
                                              validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    status = models.PositiveIntegerField(default=NEW, choices=STATUS_CHOICES, null=True, blank=True)
    payment_type = models.IntegerField(default=CASH, choices=PAYMENT_TYPE_CHOICES, null=True, blank=True)
    payment_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    hospital_reference_id = models.CharField(max_length=500, null=True, blank=True)
    insurer = models.ForeignKey(HealthInsuranceProvider, on_delete=models.DO_NOTHING, null=True, blank=True)
    tpa = models.ForeignKey(ThirdPartyAdministrator, on_delete=models.DO_NOTHING, null=True, blank=True)
    num_of_chats = models.PositiveIntegerField(null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    data = JSONField(blank=True, null=True)

    # ADMIN :Is_OpDInsured, Specialization List, appointment list
    # DEFAULTS??

    class Meta:
        db_table = "ipd_procedure_lead"

    def save(self, *args, **kwargs):
        send_lead_email = False
        if not self.id:
            send_lead_email = True
        push_to_history = False
        if self.id and self.status != self.__class__.objects.get(pk=self.id).status:
            push_to_history = True
        elif self.id is None:
            push_to_history = True
        super().save(*args, **kwargs)
        if push_to_history:
            AppointmentHistory.create(content_object=self)
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.app_commit_tasks(send_lead_email=send_lead_email))

    def app_commit_tasks(self, send_lead_email):
        from ondoc.notification.tasks import send_ipd_procedure_lead_mail
        send_ipd_procedure_lead_mail({'obj_id': self.id, 'send_email': send_lead_email})


class IpdProcedureDetailType(auth_model.TimeStampedModel):
    name = models.CharField(max_length=1000)
    priority = models.PositiveIntegerField(default=0)
    show_doctors = models.BooleanField(default=False)

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        db_table = "ipd_procedure_detail_type"


class IpdProcedureDetail(auth_model.TimeStampedModel):
    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE, null=True, verbose_name="IPD Procedure")
    detail_type = models.ForeignKey(IpdProcedureDetailType, on_delete=models.SET_NULL, null=True, verbose_name="Detail Type")
    value = models.TextField(blank=True, verbose_name="Detail")

    def __str__(self):
        return '{} - {} - {}'.format(self.ipd_procedure, self.detail_type, self.value[:25])

    class Meta:
        db_table = "ipd_procedure_details"


class ProcedureCategory(auth_model.TimeStampedModel, SearchKey):
    parents = models.ManyToManyField('self', symmetrical=False, through='ProcedureCategoryMapping',
                                     through_fields=('child_category', 'parent_category'), related_name='children')
    name = models.CharField(max_length=500, unique=True)
    details = models.CharField(max_length=2000)
    preferred_procedure = models.ForeignKey('Procedure', on_delete=models.SET_NULL,
                                            related_name='preferred_in_category', null=True, blank=True)
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "procedure_category"


class Procedure(auth_model.TimeStampedModel, SearchKey):
    categories = models.ManyToManyField(ProcedureCategory, through='ProcedureToCategoryMapping',
                                        through_fields=('procedure', 'parent_category'), related_name='procedures')
    name = models.CharField(max_length=500, unique=True)
    details = models.CharField(max_length=2000)
    duration = models.IntegerField(default=60)
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "procedure"

    @staticmethod
    def get_first_parent(all_mappings=[], parent_category_ids=None, is_primary=False):
        if parent_category_ids:
            if is_primary:
                for mapping in all_mappings:
                    if mapping.is_primary and mapping.procedure.pk in parent_category_ids:
                        return mapping
            else:
                all_mappings = sorted(all_mappings, key=lambda x: x.procedure.id)
                for mapping in all_mappings:
                    if mapping.procedure.pk in parent_category_ids:
                        return mapping
        else:
            if is_primary:
                for mapping in all_mappings:
                    if mapping.is_primary:
                        return mapping
        return None

    def get_primary_parent_category(self, parent_category_ids=None):
        parent = None
        first_parent_mapping = None
        if parent_category_ids:
            first_parent_mapping = self.get_first_parent(list(self.parent_categories_mapping.all()),
                                                         parent_category_ids, True)
            # first_parent_mapping = self.parent_categories_mapping.filter(parent_category_id__in=parent_category_ids,
            #                                                      is_primary=True).first()
            if not first_parent_mapping:
                # first_parent_mapping = self.parent_categories_mapping.filter(
                #     parent_category_id__in=parent_category_ids).order_by('procedure_id').first()
                first_parent_mapping = self.get_first_parent(list(self.parent_categories_mapping.all()),
                                                             parent_category_ids)
        if not first_parent_mapping:
            # first_parent_mapping = self.parent_categories_mapping.filter(is_primary=True).first()
            first_parent_mapping = self.get_first_parent(list(self.parent_categories_mapping.all()),
                                                         is_primary=True)
        if first_parent_mapping:
            parent = first_parent_mapping.parent_category
        return parent


class ProcedureToCategoryMapping(models.Model):
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE,
                                  related_name='parent_categories_mapping')
    parent_category = models.ForeignKey(ProcedureCategory, on_delete=models.CASCADE,
                                        related_name='procedures_mapping')
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return '({}){}'.format(self.procedure, self.parent_category)

    class Meta:
        db_table = "procedure_to_category_mapping"
        unique_together = (('procedure', 'parent_category'),)


class ProcedureCategoryMapping(models.Model):
    parent_category = models.ForeignKey(ProcedureCategory, on_delete=models.CASCADE,
                                        related_name='related_parent_category')
    child_category = models.ForeignKey(ProcedureCategory, on_delete=models.CASCADE,
                                       related_name='related_child_category')
    is_manual = models.BooleanField(default=False)  # True when the mapping is created by code and not CRM.

    def __str__(self):
        return '({}){}-{}'.format(self.parent_category, self.child_category.name, self.is_manual)

    class Meta:
        db_table = "procedure_category_mapping"
        unique_together = (('parent_category', 'child_category'),)

    @staticmethod
    def rebuild(curr_node):
        q1 = deque()
        q1.append(curr_node)
        while len(q1):
            all_objects = []
            node = q1.popleft()
            organic_children = node.related_parent_category.filter(is_manual=False).values_list('child_category',
                                                                                                flat=True)
            if organic_children:
                for child in ProcedureCategory.objects.filter(pk__in=organic_children):
                    q1.append(child)
            manual_mappings = node.related_child_category.filter(is_manual=True)
            manual_mappings.delete()
            organic_parents = node.related_child_category.filter()  # only is_manual=False left
            ancestors = set()
            for parent in organic_parents:
                for ancestor in parent.parent_category.related_child_category.filter().values_list(
                        'parent_category', flat=True):
                    ancestors.add(ancestor)
            # curr_parents = organic_parents.values_list('parent_category', flat=True)
            # curr_parents = set(curr_parents)
            # to_be_added = ancestors - curr_parents
            to_be_added = ancestors
            for manual_parent in to_be_added:
                all_objects.append(
                    ProcedureCategoryMapping(parent_category_id=manual_parent, child_category_id=node.id,
                                             is_manual=True))
            ProcedureCategoryMapping.objects.bulk_create(all_objects)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super().save(force_insert, force_update, using, update_fields)
        if not self.is_manual:
            ProcedureCategoryMapping.rebuild(self.parent_category)

    def delete(self, using=None, keep_parents=False):
        result = super().delete(using, keep_parents)
        if not self.is_manual:
            ProcedureCategoryMapping.rebuild(self.child_category)
        return result


class DoctorClinicProcedure(auth_model.TimeStampedModel):
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE, related_name="doctor_clinics_from_procedure")
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE, related_name="procedures_from_doctor_clinic")
    mrp = models.IntegerField(default=0)
    agreed_price = models.IntegerField(default=0)
    deal_price = models.IntegerField(default=0)

    def __str__(self):
        return '{} in {}'.format(str(self.procedure), str(self.doctor_clinic))

    class Meta:
        db_table = "doctor_clinic_procedure"
        unique_together = ('procedure', 'doctor_clinic')


class CommonProcedure(auth_model.TimeStampedModel):
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "{}".format(self.procedure.name)

    class Meta:
        db_table = "common_procedure"


class CommonIpdProcedure(auth_model.TimeStampedModel):
    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "{}".format(self.ipd_procedure.name)

    class Meta:
        db_table = "common_ipd_procedure"


class CommonProcedureCategory(auth_model.TimeStampedModel):
    procedure_category = models.ForeignKey(ProcedureCategory, on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "{}".format(self.procedure_category.name)

    class Meta:
        db_table = "common_procedure_category"


def get_selected_and_other_procedures(category_ids, procedure_ids, doctor=None, all=False):
    selected_procedure_ids = []
    other_procedure_ids = []
    if not all:
        if category_ids and not procedure_ids:
            all_procedures_under_category = ProcedureToCategoryMapping.objects.select_related('procedure').filter(
                parent_category_id__in=category_ids, parent_category__is_live=True, procedure__is_enabled=True).values_list('procedure_id',
                                                                                                flat=True)
            all_procedures_under_category = set(all_procedures_under_category)
            selected_procedure_ids = ProcedureCategory.objects.select_related('preferred_procedure').filter(
                pk__in=category_ids, is_live=True, preferred_procedure__is_enabled=True).values_list('preferred_procedure_id', flat=True)
            selected_procedure_ids = set(selected_procedure_ids)
            other_procedure_ids = all_procedures_under_category - selected_procedure_ids
        elif category_ids and procedure_ids:
            all_procedures_under_category = ProcedureToCategoryMapping.objects.select_related('procedure').filter(
                parent_category_id__in=category_ids, parent_category__is_live=True,
                procedure__is_enabled=True).values_list('procedure_id', flat=True)
            all_procedures_under_category = set(all_procedures_under_category)
            selected_procedure_ids = procedure_ids
            selected_procedure_ids = set(selected_procedure_ids)
            other_procedure_ids = all_procedures_under_category - selected_procedure_ids
        elif procedure_ids and not category_ids:
            selected_procedure_ids = procedure_ids
            all_parent_procedures_category_ids = ProcedureToCategoryMapping.objects.filter(
                procedure_id__in=procedure_ids).values_list('parent_category_id', flat=True)
            all_procedures_under_category = ProcedureToCategoryMapping.objects.select_related('procedure').filter(
                parent_category_id__in=all_parent_procedures_category_ids, procedure__is_enabled=True).values_list(
                'procedure_id',
                flat=True)
            all_procedures_under_category = set(all_procedures_under_category)
            selected_procedure_ids = set(selected_procedure_ids)
            other_procedure_ids = all_procedures_under_category - selected_procedure_ids
    else:
        if category_ids and not procedure_ids:
            all_clinics_of_doctor = doctor.doctor_clinics.all()
            all_procedures_under_doctor = []
            for doctor_clinic in all_clinics_of_doctor:
                all_procedures_under_doctor.extend(
                    doctor_clinic.procedures_from_doctor_clinic.filter(procedure__is_enabled=True).values_list(
                        'procedure_id', flat=True))
            all_procedures_under_doctor = set(all_procedures_under_doctor)
            selected_procedure_ids = ProcedureCategory.objects.select_related('preferred_procedure').filter(
                pk__in=category_ids, is_live=True, preferred_procedure__is_enabled=True).values_list(
                'preferred_procedure_id', flat=True)
            selected_procedure_ids = set(selected_procedure_ids)
            other_procedure_ids = all_procedures_under_doctor - selected_procedure_ids
        elif category_ids and procedure_ids:
            all_clinics_of_doctor = doctor.doctor_clinics.all()
            all_procedures_under_doctor = []
            for doctor_clinic in all_clinics_of_doctor:
                all_procedures_under_doctor.extend(
                    doctor_clinic.procedures_from_doctor_clinic.filter(procedure__is_enabled=True).values_list('procedure_id',
                                                                                                        flat=True))
            all_procedures_under_doctor = set(all_procedures_under_doctor)
            selected_procedure_ids = procedure_ids
            selected_procedure_ids = set(selected_procedure_ids)
            other_procedure_ids = all_procedures_under_doctor - selected_procedure_ids
        elif procedure_ids and not category_ids:
            selected_procedure_ids = procedure_ids
            all_clinics_of_doctor = doctor.doctor_clinics.all()
            all_procedures_under_doctor = []
            for doctor_clinic in all_clinics_of_doctor:
                all_procedures_under_doctor.extend(
                    doctor_clinic.procedures_from_doctor_clinic.filter(procedure__is_enabled=True).values_list(
                        'procedure_id', flat=True))
            all_procedures_under_doctor = set(all_procedures_under_doctor)
            selected_procedure_ids = set(selected_procedure_ids)
            other_procedure_ids = all_procedures_under_doctor - selected_procedure_ids
        else:
            all_clinics_of_doctor = doctor.doctor_clinics.all()
            all_procedures_under_doctor = []
            for doctor_clinic in all_clinics_of_doctor:
                all_procedures_under_doctor.extend(
                    doctor_clinic.procedures_from_doctor_clinic.filter(procedure__is_enabled=True).values_list('procedure_id', flat=True))
            all_procedures_under_doctor = set(all_procedures_under_doctor)
            selected_procedure_ids = []
            selected_procedure_ids = set(selected_procedure_ids)
            other_procedure_ids = all_procedures_under_doctor - selected_procedure_ids

    return selected_procedure_ids, other_procedure_ids


def get_included_doctor_clinic_procedure(all_data, filter_ids):
        return [dcp for dcp in all_data if dcp.procedure.id in filter_ids]

def get_procedure_categories_with_procedures(selected_procedures, other_procedures):
    temp_result = OrderedDict()
    all_procedures = selected_procedures + other_procedures
    for procedure in all_procedures:
        temp_category_id = procedure.pop('procedure_category_id')
        temp_category_name = procedure.pop('procedure_category_name')
        if temp_category_id in temp_result:
            temp_result[temp_category_id]['procedures'].append(procedure)
        else:
            temp_result[temp_category_id] = OrderedDict()
            temp_result[temp_category_id]['name'] = temp_category_name
            temp_result[temp_category_id]['procedures'] = [procedure]

    final_result = []
    for key, value in temp_result.items():
        value['procedure_category_id'] = key
        final_result.append(value)

    return final_result


class IpdProcedureSynonym(auth_model.TimeStampedModel):
    name = models.CharField(max_length=1000, default='')

    def __str__(self):
        return self.name

    class Meta:
        db_table = "ipd_procedure_synonym"


class IpdProcedureSynonymMapping(auth_model.TimeStampedModel):
    ipd_procedure_synonym = models.ForeignKey(IpdProcedureSynonym, on_delete=models.CASCADE)
    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE)
    order = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = "procedure_synonym_mapping"


class SimilarIpdProcedureMapping(auth_model.TimeStampedModel):
    ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE, related_name='similar_ipds')
    similar_ipd_procedure = models.ForeignKey(IpdProcedure, on_delete=models.CASCADE, related_name='similar_ipds_2')
    order = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "similar_ipd_procedure_mapping"
        unique_together = (('ipd_procedure', 'similar_ipd_procedure'),)
