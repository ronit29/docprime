import re

from django.http import QueryDict
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response

from ondoc.api.v1.doctor.serializers import DoctorListSerializer
from ondoc.banner.models import Banner


class BannerListViewSet(viewsets.GenericViewSet):

    def list(self, request):
        parameters = request.query_params

        # try:
        #
        #     choice_id = parameters.get('choice_id', None)
        #     if choice_id:
        #         choice_id = set(choice_id)
        #
        # except:
        #     return Response([], status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()

        queryset = Banner.objects.filter(enable=True, start_date__lte=now, end_date__gte=now).order_by('-priority')[:10]



        slider_action = dict(Banner.slider_choice)
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
            resp1 = dict()
            if data.url:
                data.url = re.sub('.*?\?', '', data.url)
                qd = QueryDict(data.url)
                # resp1['specialization_ids'] = qd.get('specialization_ids')
                # resp1['specializations'] = qd.get('specializations')
                # resp1['test_ids'] = qd.get('test_ids')
                # resp1['network_id'] = qd.get('network_id')
                # resp1['place_id'] = qd.get('place_id')
                # resp1['sits_at'] = qd.get('sits_at')
                # resp1['procedure_ids'] = qd.get('procedure_ids')
                # resp1['is_available'] = qd.get('is_available')
                # resp1['procedure_category_ids'] = qd.get('procedure_category_ids')
                # resp1['latitude'] = qd.get('latitude')
                # resp1['longitude'] = qd.get('longitude')
                # resp1['page_id'] = qd.get('page')
                # resp1['min_distance'] = qd.get('min_distance')
                # resp1['max_distance'] = qd.get('max_distance')
                # resp1['condition_ids'] = qd.get('condition_ids')
                # resp1['min_fees'] = qd.get('min_fees')
                # resp1['max_fees'] = qd.get('max_fees')
                # resp1['sort_on'] = qd.get('sort_on')
                # resp1['is_female'] = qd.get('is_female')
                resp['url_details'] = qd
            resp['image'] = request.build_absolute_uri(data.image.url)

            final_result.append(resp)

        return Response(final_result)

