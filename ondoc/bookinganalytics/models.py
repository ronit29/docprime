from django.db import models
from django.utils import timezone
# Create your models here.

# Model of City at Optimus end, this model points to table in mssql server in optimus server.
class DP_CityMaster(models.Model):

    CreatedOn = models.DateTimeField(auto_now_add=True)
    CityId = models.IntegerField(primary_key=True)
    CityName = models.CharField(null=True, blank=True, max_length=500)
    IsActive = models.BooleanField(default=True)

    def __str__(self):
        return str(self.CityId)

    class Meta:
        db_table = "DP_CityMaster"
        managed = False

# Model of State at Optimus end, this model points to table in mssql server in optimus server.
class DP_StateMaster(models.Model):

    StateId = models.IntegerField(primary_key=True)
    StateName = models.CharField(null=True, blank=True, max_length=500)
    IsActive = models.BooleanField(default=True)
    CreatedOn = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.StateId)


    # def __repr__(self):
    #     return str(self.StateId)

    class Meta:
        db_table = "DP_StateMaster"
        managed = False


# Model of Speciality at Optimus end, this model points to table in mssql server in optimus server.
class DP_SpecialityMaster(models.Model):
    SpecialityId = models.IntegerField(null=True, blank=False)
    Speciality = models.CharField(null=True, blank=True, max_length=500)
    IsActive = models.BooleanField(default=True)
    CreatedOn = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.SpecialityId)

    class Meta:
        db_table = "DP_SpecialityMaster"
        managed = False

# Model of OpdStatus at Optimus end, this model points to table in mssql server in optimus server.
class DP_OPDStatusMaster(models.Model):
    OPDStatusId = models.IntegerField(null=True, blank=False)
    OPDStatus = models.CharField(null=True, blank=True, max_length=500)
    IsActive = models.BooleanField(default=True)
    CreatedOn = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.OPDStatusId)

    class Meta:
        db_table = "DP_OPDStatusMaster"
        managed = False


# Model of opd consult and tests at Optimus end, this model points to table in mssql server in optimus server.
class DP_OpdConsultsAndTests(models.Model):

    Appointment_Id = models.BigIntegerField(primary_key=True)
    StatusId = models.IntegerField(null=True, blank=True)
    TypeId = models.IntegerField(null=True, blank=True)
    GMValue = models.IntegerField(null=True, blank=True)
    PromoCost = models.IntegerField(null=True, blank=True)
    CreatedOn = models.DateTimeField(auto_now_add=True)
    PaymentType = models.SmallIntegerField(null=True, blank=True)
    Payout = models.IntegerField(null=True, blank=True)
    SpecialityId = models.IntegerField(null=True, blank=True)
    Category = models.IntegerField(null=True, blank=True)
    ProviderId = models.IntegerField(null=True, blank=True)
    CityId = models.IntegerField(null=True, blank=True)
    StateId = models.IntegerField(null=True, blank=True)
    IsActive = models.BooleanField(default=True)
    CashbackUsed = models.IntegerField(null=True, blank=True)
    BookingDate = models.DateTimeField(null=True, blank=True)
    CorporateDealId = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return str(self.Appointment_Id)

    def __repr__(self):
        return str(self.Appointment_Id)

    class Meta:
        db_table = "DP_OpdConsultsAndTests"
        managed = False


# Model of under writing details at Optimus end, this model points to table in mssql server in optimus server.
class DP_UnderWritingDetails(models.Model):

    UnderWritingId = models.BigIntegerField(primary_key=True)
    CaseId = models.IntegerField(null=True, blank=True)
    InsurerId = models.IntegerField(null=True, blank=True)
    CreatedOn = models.DateTimeField()
    StatusId = models.IntegerField(null=True, blank=True)
    IsActive = models.BooleanField(default=True)

    def __str__(self):
        return str(self.UnderWritingId)

    class Meta:
        db_table = "DP_UnderWritingDetails"
        managed = False


# Model of Insurer at Optimus end, this model points to table in mssql server in optimus server.
class DP_InsurerMaster(models.Model):
    InsurerMasterId = models.BigIntegerField(primary_key=True)
    InsurerId = models.IntegerField(null=True, blank=True)
    InsurerName = models.CharField(null=True, blank=True, max_length=500)
    IsActive = models.BooleanField(default=False)
    CreatedOn = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.InsurerMasterId)

    class Meta:
        db_table = "DP_InsurerMaster"
        managed = False


# Model of TeleD status at Optimus end, this model points to table in mssql server in optimus server.
class DP_TeleDStatusMaster(models.Model):
    TeleStatusId = models.BigIntegerField(null=True, blank=False)
    TeleStatus = models.CharField(null=True, blank=True, max_length=500)
    IsActive = models.BooleanField(default=True)
    CreatedOn = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.TeleStatusId)

    class Meta:
        db_table = "DP_TeleDStatusMaster"
        managed = False

# Model of Tele deal at Optimus end, this model points to table in mssql server in optimus server.
class TeleDeal(models.Model):
    TeleDealId = models.BigIntegerField(primary_key=True)
    InsurerId = models.IntegerField(null=True, blank=True)
    Fees = models.IntegerField(null=True, blank=True)
    Tax = models.IntegerField(null=True, blank=True)
    DealStartDate = models.DateTimeField()
    DealEndDate = models.DateTimeField()
    CreatedOn = models.DateTimeField(auto_now_add=True)
    IsActive = models.BooleanField(default=True)

    def __str__(self):
        return str(self.TeleDealId)

    class Meta:
        db_table = "TeleDeal"
        managed = False


class DP_CorporateDeals(models.Model):
    CorporateDealId = models.BigIntegerField(primary_key=True)
    CorporateName = models.CharField(max_length=5000, null=True, blank=True)
    DealStartDate = models.DateTimeField()
    DealEndDate = models.DateTimeField()
    GrossAmount = models.IntegerField(null=True, blank=True)
    ExpectedProviderFee = models.IntegerField(null=True, blank=True)
    NumberOfEmployees = models.IntegerField(null=True, blank=True)
    PaymentDate = models.DateTimeField()
    TDSDeducted = models.CharField(max_length=5000, null=True, blank=True)
    ReceiptNumber = models.CharField(max_length=5000, null=True, blank=True)
    IsActive = models.BooleanField(default=False)
    CreatedDate = models.DateTimeField()
    UpdatedDate = models.DateTimeField()

    def __str__(self):
        return str(self.CorporateDealId)

    class Meta:
        db_table = "DP_CorporateDeals"
        managed = False