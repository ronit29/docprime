from rest_framework import viewsets, status
from rest_framework.response import Response

from ondoc.banner.models import Banner


class BannerListViewSet(viewsets.GenericViewSet):

    def list(self, request):
        parameters = request.query_params

        try:

            choice_id = parameters.get('choice_id', None)
            if choice_id:
                choice_id = set(choice_id)

        except:
            return Response([], status=status.HTTP_400_BAD_REQUEST)


        queryset = Banner.objects.filter(slider_locate__in=choice_id, enable = True)
        resp = dict()
        slider_action = dict(Banner.slider_choice)
        slider_locate = dict(Banner.slider_location)
        final_result = []
        for data in queryset:
            resp['title'] = data.title
            resp['id'] = data.id
            resp['slider_location'] = slider_locate[data.slider_locate]
            resp['slider_action'] = slider_action[data.slider_action]
            resp['start_date'] = data.start_date
            resp['end_date'] = data.end_date
            resp['event_name'] = data.event_name
            resp['latitude'] = data.latitude
            resp['longitude'] = data.longitude
            resp['url'] = data.url
            resp['object_id'] = data.object_id
            resp['image'] = data.image.url

        final_result.append({'banner_content': resp})

        return Response(final_result)

