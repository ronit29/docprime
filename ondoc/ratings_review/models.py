from django.contrib.gis.db import models
from ondoc.authentication import models as auth_model
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

import logging

logger = logging.getLogger(__name__)


class RatingsReview(auth_model.TimeStampedModel):
    LAB = 1
    OPD = 2
    APPOINTMENT_TYPE_CHOICES = [(LAB, 'Lab'), (OPD, 'Opd')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ratings = models.PositiveIntegerField(null=True)
    review = models.CharField(max_length=500, null=True, blank=True)
    appoitnment_id = models.PositiveIntegerField(blank=True, null=True)
    appoitnment_type = models.PositiveSmallIntegerField(choices=APPOINTMENT_TYPE_CHOICES, blank=True, null=True)
    is_live = models.BooleanField(default=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    class Meta:
        db_table = 'ratings_review'


class ReviewActions(auth_model.TimeStampedModel):
    NOACTION = 0
    LIKE = 1
    DISLIKE = 2
    REPORT = 3
    ACTION_CHOICES = [(NOACTION, "NoAction"), (LIKE, "Like"), (DISLIKE, "Dislike"), (REPORT, "Report")]

    action = models.PositiveIntegerField(default=NOACTION, choices=ACTION_CHOICES)
    rating = models.OneToOneField(RatingsReview, blank=True, null=True, on_delete=models.CASCADE)

    class Meta:
        db_table = 'review_action'

