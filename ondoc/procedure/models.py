from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.doctor.models import DoctorClinic, SearchKey
from collections import deque, OrderedDict


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
