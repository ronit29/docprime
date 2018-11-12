from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.doctor.models import DoctorClinic, SearchKey
from collections import deque


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
    duration = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "procedure"

    def get_primary_parent_category(self):
        parent = None
        temp_primary = ProcedureToCategoryMapping.objects.filter(is_primary=True, procedure=self).first()
        if temp_primary:
            parent = temp_primary.parent_category
        elif self.categories.count():
            parent = self.categories.all().first()
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
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE)
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE)
    mrp = models.IntegerField(default=0)
    agreed_price = models.IntegerField(default=0)
    deal_price = models.IntegerField(default=0)

    class Meta:
        db_table = "doctor_clinic_procedure"
        unique_together = ('procedure', 'doctor_clinic')


class CommonProcedureCategory(auth_model.TimeStampedModel):
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "{}".format(self.procedure.name)

    class Meta:
        db_table = "common_procedure_category"
