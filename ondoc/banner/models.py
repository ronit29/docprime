from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.contrib.postgres.fields import JSONField

from ondoc.authentication import models as auth_model
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import re
from urllib.parse import urlparse
from django.http import QueryDict
from django.utils import timezone
from django.db.models import Q


class SliderLocation(models.Model):
    name = models.CharField(max_length=1000, null=True, default='Home_Page')

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'slider_location'


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
    location = models.ForeignKey(SliderLocation, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=500)
    image = models.ImageField('Banner image', upload_to='banner/images')
    url = models.URLField(max_length=10000, null=True, blank=True, verbose_name='landing url')
    url_params_included = JSONField(null=True, blank=True, help_text='JSON format example: {"specialization_id": [3667, 4321], "test_ids": [87], "is_package": True, "Name": "Stringvalue"}')
    url_params_excluded = JSONField(null=True, blank=True, help_text='JSON format example: {"specialization_id": [3667, 4321], "test_ids": [87], "is_package": True, "Name": "Stringvalue"}')
    priority = models.PositiveIntegerField(blank=True, null=True, default=0)
    slider_locate = models.SmallIntegerField(choices=slider_location, default=1, null=True, blank=True) # Do not use
    slider_action = models.SmallIntegerField(choices=slider_choice, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    enable = models.BooleanField(verbose_name='is enabled', default=True)
    event_name = models.CharField(max_length=1000)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    radius = models.FloatField(null=True, blank=True)
    show_in_app = models.BooleanField(default=True)
    app_screen = models.CharField(max_length=1000, null=True, blank=True)
    app_params = JSONField(null=True, blank=True)


    def __str__(self):
        return self.title

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        # slider_locate_choices = dict(self.location.name)
        # self.event_name = self.title+'_'+ str(slider_locate[self.slider_locate])
        if self.location.name:
            self.event_name = '_'.join(self.title.lower().split())\
                              + '_' \
                              + '_'.join(
                self.location.name.lower().split())
            # self.slider_locate = self.location.name
            super().save(force_insert, force_update, using, update_fields)
        else:
            super().save(force_insert, force_update, using, update_fields)


    @staticmethod
    def get_all_banners(request):

        queryset = Banner.objects.filter(enable=True).filter(Q(start_date__lte=timezone.now()) | Q(start_date__isnull=True)).filter(Q(end_date__gte=timezone.now()) | Q(end_date__isnull=True)).order_by('-priority')[:100]
        #queryset = Banner.objects.filter(enable=True)
        slider_locate = dict(Banner.slider_location)
        final_result = []
        for data in queryset:
            resp = dict()
            resp['title'] = data.title
            resp['id'] = data.id
            # resp['slider_location'] = slider_locate[data.slider_locate]
            resp['slider_location'] = data.location.name if data.location and data.location.name else None
            resp['latitude'] = data.latitude
            resp['longitude'] = data.longitude
            resp['radius'] = data.radius
            resp['start_date'] = data.start_date
            resp['end_date'] = data.end_date
            resp['priority'] = data.priority
            resp['url_params_included'] = data.url_params_included
            resp['url_params_excluded'] = data.url_params_excluded
            resp['show_in_app'] = data.show_in_app
            resp['app_params'] = data.app_params
            resp['app_screen'] = data.app_screen
            resp['event_name'] = data.event_name
            resp['url'] = None
            resp['url_details'] = None
            if data.url:
                path = urlparse(data.url).path
                params = urlparse(data.url).params + '?'
                query = urlparse(data.url).query
                netloc = urlparse(data.url).netloc
                if re.match(r'.*?docprime.com/?', netloc):
                    if path:
                        resp['url'] = path + params + query
                    else:
                        resp['url'] = '/'
                else:
                    resp['url'] = data.url
            if data.url:
                data.url = re.sub('.*?\?', '', data.url)
                qd = QueryDict(data.url, mutable=True)

                for key in qd.keys():
                    if qd[key] and qd[key]=='true':
                        qd[key] = True
                    elif qd[key] and qd[key]=='false':
                        qd[key] = False

                resp['url_details'] = qd
            resp['image'] = request.build_absolute_uri(data.image.url)

            final_result.append(resp)
        return final_result

    class Meta:
        db_table = 'banner'
