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


        queryset = Banner.objects.filter(slider_location__in=choice_id)

