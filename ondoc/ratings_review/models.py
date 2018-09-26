from django.contrib.gis.db import models
from ondoc.authentication import models as auth_model
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

import logging

logger = logging.getLogger(__name__)


class RatingsReview(auth_model.TimeStampedModel):
    LIKE = 1
    DISLIKE = 2
    REPORT = 3
    ACTION_STATUS = [(LIKE, "Like"), (DISLIKE, "Dislike"), (REPORT, "Report")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ratings = models.PositiveIntegerField(null=False)
    review = models.CharField(max_length=500, null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    class Meta:
        db_table = 'ratings_review'

