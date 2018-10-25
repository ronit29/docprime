from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.doctor.models import DoctorClinic, SearchKey


class ProcedureCategory(auth_model.TimeStampedModel, SearchKey):
    parents = models.ManyToManyField('self', through='ProcedureCategoryMapping',
                                     through_fields=('child_category', 'parent_category'))
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
    parent_category = models.ForeignKey(ProcedureCategory)
    child_category = models.ForeignKey(ProcedureCategory)
    is_manual = models.BooleanField(default=False)

    def __str__(self):
        return '({}){}-{}'.format(self.parent_category, self.child_category.name, self.is_manual)

    class Meta:
        db_table = "procedure_category_mapping"


class DoctorClinicProcedure(auth_model.TimeStampedModel):
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE)
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    listing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = "doctor_clinic_procedure"
        unique_together = ('procedure', 'doctor_clinic')
