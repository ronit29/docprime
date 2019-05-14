from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.contrib.postgres.fields import JSONField
from django.utils.safestring import mark_safe

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

from ondoc.doctor.models import OpdAppointment
from ondoc.notification.models import NotificationAction
from django.contrib.postgres.fields import ArrayField
from multiselectfield import MultiSelectField


class SliderLocation(models.Model):
    name = models.CharField(max_length=1000, null=True, default='Home_Page')

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'slider_location'


class RecommenderThrough(auth_model.TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey()

    recommender = models.ForeignKey('banner.Recommender', related_name="through_data", on_delete=models.CASCADE)


class Recommender(auth_model.TimeStampedModel):

    payment_type = MultiSelectField(choices=OpdAppointment.PAY_CHOICES, null=True, blank=True)
    notification_type = MultiSelectField(choices=NotificationAction.NOTIFICATION_TYPE_CHOICES, null=True, blank=True)
    item_min_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    item_max_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'recommender'


class EmailBanner(auth_model.TimeStampedModel):

    key = models.CharField(max_length=500, unique=True)
    data = JSONField(blank=True, null=True)
    properties = GenericRelation('banner.RecommenderThrough', related_name="email_banners")
    enable_login = models.BooleanField(default=False)
    banner_image = models.FileField(upload_to="banner/email_banner", null=True, blank=True)
    banner_url = models.CharField(max_length=1000, blank=True, null=True)

    @classmethod
    def get_banner(cls, appointment=None, notification_type=None):

        qs = RecommenderThrough.objects.select_related('recommender')\
                                       .filter(content_type_id=ContentType.objects.get_for_model(cls))

        if appointment and appointment.payment_type:
            qs = qs.filter(recommender__payment_type__contains=appointment.payment_type)

        if notification_type:
            qs = qs.filter(recommender__notification_type__contains=notification_type)

        if appointment and appointment.deal_price:
            deal_price = appointment.deal_price
            qs = qs.filter(Q(recommender__item_min_price__isnull=True) | Q(recommender__item_min_price__lte=deal_price))
            qs = qs.filter(Q(recommender__item_max_price__isnull=True) | Q(recommender__item_max_price__gte=deal_price))

        banner = None
        through_row = qs.first()
        if through_row:
            banner = through_row.content_object
            banner = banner.build_banner_html(appointment.user)

        return banner

    def build_banner_html(self, user=None):
        from ondoc.authentication.models import AgentToken

        href = self.banner_url
        src = ""

        if self.banner_image and self.banner_image.url:
            src = self.banner_image.url

        if self.enable_login and user and href:
            token = AgentToken.objects.create_token(user)
            href += "&access_token=" + str(token.token)

        if not href or not src:
            return None

        html = ''''<tr><td><table cellpadding="0" cellspacing="0" style="width: 100%; padding: 10px 15px;"><tbody><tr><td style="width: 0%; text-align: center;"><a href="{}" target="_blank"><img src="{}"></a></td></tr></tbody></table></td></tr>'''.format(href, src)
        html = mark_safe(html)

        return html


    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        app = OpdAppointment.objects.first()
        EmailBanner.get_banner(app, 1)

    def __str__(self):
        return self.key

    class Meta:
        db_table = 'email_banner'


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
