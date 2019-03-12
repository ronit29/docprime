import datetime
from django.db import models, transaction
from ondoc.authentication import models as auth_model
from ondoc.authentication.models import User
from ondoc.diagnostic.models import LabNetwork, Lab, LabTest
# Create your models here.


class Plan(auth_model.TimeStampedModel):
    name = models.CharField(max_length=50)
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    deal_price = models.DecimalField(max_digits=10, decimal_places=2)
    unlimited_online_consultation = models.BooleanField(default=True)
    priority_queue = models.BooleanField(default=True)

    class Meta:
        db_table = "subscription_plan"

    def __str__(self):
        return self.name


class PlanFeature(auth_model.TimeStampedModel):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="plan_features")
    count = models.PositiveIntegerField(verbose_name="Times per year?")
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE)

    class Meta:
        db_table = "subscription_plan_feature"


class UserPlanMapping(auth_model.TimeStampedModel):
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, related_name="subscribed_user_mapping")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="plan_mapping", unique=True)
    is_active = models.BooleanField(default=True)
    expire_at = models.DateTimeField()

    class Meta:
        db_table = "subscription_plan_user"

    def save(self, *args, **kwargs):
        if not self.expire_at:
            self.expire_at = self.created_at + datetime.timedelta(days=365)
        super().save(*args, **kwargs)
