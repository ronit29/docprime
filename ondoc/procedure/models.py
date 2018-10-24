from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.doctor.models import DoctorClinic


class Procedure(auth_model.TimeStampedModel):
    name = models.CharField(max_length=500, unique=True)
    details = models.CharField(max_length=2000)
    duration = models.IntegerField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = "procedure"


class DoctorClinicProcedure(auth_model.TimeStampedModel):
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE)
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    listing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = "doctor_clinic_procedure"
        unique_together = ('procedure', 'doctor_clinic')
