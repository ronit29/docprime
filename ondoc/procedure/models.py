from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.doctor.models import DoctorClinic, SearchKey


class ProcedureCategory(auth_model.TimeStampedModel, SearchKey):
    parents = models.ManyToManyField('self', symmetrical=False, through='ProcedureCategoryMapping',
                                     through_fields=('child_category', 'parent_category'), related_name='children')
    name = models.CharField(max_length=500, unique=True)
    details = models.CharField(max_length=2000)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "procedure_category"


class Procedure(auth_model.TimeStampedModel, SearchKey):
    categories = models.ManyToManyField(ProcedureCategory)
    name = models.CharField(max_length=500, unique=True)
    details = models.CharField(max_length=2000)
    duration = models.IntegerField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = "procedure"


class ProcedureCategoryMapping(models.Model):
    parent_category = models.ForeignKey(ProcedureCategory, on_delete=models.CASCADE, related_name='related_parent_category')
    child_category = models.ForeignKey(ProcedureCategory, on_delete=models.CASCADE, related_name='related_child_category')
    is_manual = models.BooleanField(default=False)  # added by code

    def __str__(self):
        return '({}){}-{}'.format(self.parent_category, self.child_category.name, self.is_manual)

    class Meta:
        db_table = "procedure_category_mapping"
        unique_together = ('parent_category', 'child_category')

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super().save(force_insert, force_update, using, update_fields)
        parents = ProcedureCategoryMapping.objects.filter(child_category=self.parent_category).distinct()
        all_objects = []
        for i in parents:
            all_objects.append(ProcedureCategoryMapping(parent_category=i.parent_category, child_category=self.child_category, is_manual=True))
        ProcedureCategoryMapping.objects.bulk_create(all_objects)

    def delete(self, using=None, keep_parents=False):
        return super().delete(using, keep_parents)


class DoctorClinicProcedure(auth_model.TimeStampedModel):
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE)
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    listing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = "doctor_clinic_procedure"
        unique_together = ('procedure', 'doctor_clinic')
