from django.contrib.gis.db import models
from ondoc.authentication import models as auth_model
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Banner(auth_model.TimeStampedModel):
    TEST = 1
    PROCEDURES = 2
    SPECIALIZATION = 3
    PROCEDURE_CATEGORY = 4
    CONDITION = 5
    slider_choice = [(TEST, 'test'), (PROCEDURES, 'procedure'), (PROCEDURE_CATEGORY, 'procedure_category'), (SPECIALIZATION, 'specialization'), (CONDITION, 'condition')]
    HOME_PAGE = 1
    DOCTOR_RESULT = 2
    LAB_RESULT = 3

    slider_location = [(HOME_PAGE, 'home_page'), (DOCTOR_RESULT, 'doctor_search_page'), (LAB_RESULT, 'lab_search_page')]
    title = models.CharField(max_length=500)
    image = models.ImageField('Banner image', upload_to='banner/images')
    url = models.URLField(blank=True)
    # slider_id = models.PositiveSmallIntegerField(blank=True, null=True, unique=True)
    slider_locate = models.SmallIntegerField(choices=slider_location)
    slider_action = models.SmallIntegerField(choices=slider_choice)
    object_id = models.PositiveIntegerField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    enable = models.BooleanField(verbose_name='is enabled', default=True)
    event_name = models.CharField(max_length=1000)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.title

    class Meta:
        db_table = 'banner'


