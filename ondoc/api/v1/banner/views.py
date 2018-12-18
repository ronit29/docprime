import re
from django.http import QueryDict
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from ondoc.banner.models import Banner


class BannerListViewSet(viewsets.GenericViewSet):

    def list(self, request):
        parameters = request.query_params

        now = timezone.now()

        queryset = Banner.objects.filter(enable=True, start_date__lte=now, end_date__gte=now).order_by('-priority')[:10]
        slider_locate = dict(Banner.slider_location)
        final_result = []

        for data in queryset:
            resp = dict()
            resp['title'] = data.title
            resp['id'] = data.id
            resp['slider_location'] = slider_locate[data.slider_locate]
            resp['start_date'] = data.start_date
            resp['end_date'] = data.end_date
            resp['priority'] = data.priority
            resp['event_name'] = data.event_name
            resp['url'] = data.url
            if data.url:
                data.url = re.sub('.*?\?', '', data.url)
                qd = QueryDict(data.url)
                resp['url_details'] = qd
            resp['image'] = request.build_absolute_uri(data.image.url)

            final_result.append(resp)

        return Response(final_result)

