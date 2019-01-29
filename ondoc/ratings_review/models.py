from django.contrib.gis.db import models
from ondoc.authentication import models as auth_model
# from ondoc.ratings_review.models import ReviewCompliments
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

import logging

logger = logging.getLogger(__name__)


class ReviewCompliments(auth_model.TimeStampedModel):
    LAB = 1
    DOCTOR = 2
    TYPE_CHOICES = [(LAB, 'Lab'), (DOCTOR, 'Opd')]
    message = models.CharField(max_length=128, default=None)
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES, blank=True, null=True)
    rating_level = models.PositiveSmallIntegerField(default=None)
    icon = models.ImageField(upload_to='rating_compliments/icons', null=True, blank=True, default='')

    class Meta:
        db_table = 'review_compliments'

    def __str__(self):
        return '{}-{}'.format(self.message, self.rating_level)


class RatingsReview(auth_model.TimeStampedModel):
    LAB = 1
    OPD = 2
    APPROVED = 1
    PENDING = 2
    DENIED = 3
    APPOINTMENT_TYPE_CHOICES = [(LAB, 'Lab'), (OPD, 'Opd')]
    MODERATION_TYPE_CHOICES = [(APPROVED, 'Approved'), (PENDING, 'Pending'), (DENIED, 'Denied')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ratings = models.PositiveIntegerField(null=True)
    review = models.CharField(max_length=5000, null=True, blank=True)
    appointment_id = models.PositiveIntegerField(blank=True, null=True)
    appointment_type = models.PositiveSmallIntegerField(choices=APPOINTMENT_TYPE_CHOICES, blank=True, null=True)
    is_live = models.BooleanField(default=True)
    compliment = models.ManyToManyField(ReviewCompliments, related_name='compliment_review')
    moderation_status = models.PositiveSmallIntegerField(choices=MODERATION_TYPE_CHOICES, blank=True, default=PENDING)
    moderation_comments = models.CharField(max_length=1000, null=True, blank=True)
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
    rating = models.ForeignKey(RatingsReview, blank=True, null=True, on_delete=models.CASCADE)

    class Meta:
        db_table = 'review_action'


