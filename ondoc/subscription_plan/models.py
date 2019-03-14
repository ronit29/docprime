import datetime
from django.db import models, transaction
from django.utils import timezone

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
    features = models.ManyToManyField('PlanFeature', through='PlanFeatureMapping', through_fields=('plan', 'feature'),
                                      related_name='plans_included_in')
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "subscription_plan"

    def __str__(self):
        return self.name


class PlanFeature(auth_model.TimeStampedModel):
    name = models.CharField(max_length=150, default='')
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE, null=True, blank=True)
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, null=True, blank=True)
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "subscription_plan_feature"

    def __str__(self):
        return self.name

    # def __str__(self):
    #     output = ''
    #     if self.network:
    #         output += self.network.name
    #     if self.lab:
    #         output += self.lab.name
    #     if self.test:
    #         output += self.test.name
    #     return output


class PlanFeatureMapping(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="feature_mappings")
    feature = models.ForeignKey(PlanFeature, on_delete=models.CASCADE, related_name="plan_mappings")
    count = models.PositiveIntegerField(verbose_name="Times per year?")
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = (('plan', 'feature'),)


class UserPlanMapping(auth_model.TimeStampedModel):
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, related_name="subscribed_user_mapping")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="plan_mapping", unique=True)
    is_active = models.BooleanField(default=True)
    expire_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "subscription_plan_user"

    def save(self, *args, **kwargs):
        if not self.expire_at:
            self.expire_at = timezone.now() + datetime.timedelta(days=365)
            super().save(*args, **kwargs)
        super().save(*args, **kwargs)

