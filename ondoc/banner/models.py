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
    slider_choice = [(TEST, 'Test'), (PROCEDURES, 'Procedure'), (PROCEDURE_CATEGORY, 'Procedure Category'),
                     (SPECIALIZATION, 'Specialization'), (CONDITION, 'Condition')]
    HOME_PAGE = 1
    DOCTOR_RESULT = 2
    LAB_RESULT = 3
    PACKAGE = 4
    PROCEDURE = 5
    OFFERS_PAGE = 6

    slider_location = [(HOME_PAGE, 'home_page'), (DOCTOR_RESULT, 'doctor_search_page'), (LAB_RESULT, 'lab_search_page'), (PROCEDURE, 'procedure_search_page'), (PACKAGE, 'package_search_page'),
                       (OFFERS_PAGE, 'offers_page')]
    title = models.CharField(max_length=500)
    image = models.ImageField('Banner image', upload_to='banner/images')
    url = models.URLField(max_length=10000, null=True, blank=True)
    priority = models.PositiveIntegerField(blank=True, null=True, default=0)
    slider_locate = models.SmallIntegerField(choices=slider_location)
    slider_action = models.SmallIntegerField(choices=slider_choice, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    enable = models.BooleanField(verbose_name='is enabled', default=True)
    event_name = models.CharField(max_length=1000)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    show_in_app = models.BooleanField(default=True)
    app_screen = models.CharField(max_length=1000, null=True, blank=True)
    app_params = models.CharField(max_length=10000, null=True, blank=True)



    def __str__(self):
        return self.title

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        slider_locate_choices = dict(self.slider_location)
        # self.event_name = self.title+'_'+ str(slider_locate[self.slider_locate])
        self.event_name = '_'.join(self.title.lower().split())\
                          + '_' \
                          + '_'.join(
            str(slider_locate_choices[self.slider_locate]).lower().split())
        super().save(force_insert, force_update, using, update_fields)


    class Meta:
        db_table = 'banner'
