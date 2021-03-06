import re
from urllib.parse import urlparse

from django.contrib.gis.geos import Point
from django.http import QueryDict
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ondoc.authentication.backends import JWTAuthentication
from ondoc.banner.models import Banner
from ondoc.common.middleware import use_slave
from django.db.models import Q

class BannerListViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)

    def get_queryset(self):
        return None

    @use_slave
    def list(self, request):
        parameters = request.query_params
        lat = parameters.get('lat', None)
        long = parameters.get('long', None)
        from_app = parameters.get('from_app', False)
        if from_app == 'True' or from_app == 'true':
            from_app = True
        else:
            from_app = False
        queryset = Banner.objects.prefetch_related('banner_location', 'location').filter(enable=True).filter(
            Q(start_date__lte=timezone.now()) | Q(start_date__isnull=True)).filter(
            Q(end_date__gte=timezone.now()) | Q(end_date__isnull=True)).order_by('-priority')[:100]
        banners = Banner.get_all_banners(request, lat, long, from_app, queryset)
        return Response(banners)
        # res = []
        # for banner_obj in banners:
        #     # if not banner_obj.get('latitude') or not banner_obj.get('longitude') or not banner_obj.get('radius'):
        #     #     res.append(banner_obj)
        #     elif lat and long:
        #         if banner_obj.get('latitude') and banner_obj.get('longitude') and banner_obj.get('radius'):
        #             latitude = banner_obj.get('latitude')
        #             longitude = banner_obj.get('longitude')
        #             radius = banner_obj.get('radius')  # Radius in kilo-metres
        #             pnt1 = Point(float(longitude), float(latitude))
        #             try:
        #                 pnt2 = Point(float(long), float(lat))
        #             except:
        #                 return Response({'msg': 'Invalid Lat Long'}, status=status.HTTP_400_BAD_REQUEST)

        #             distance = pnt1.distance(pnt2)*100  # Distance in kilo-metres
        #             if distance <= radius:
        #                 res.append(banner_obj)
        #         else:
        #             res.append(banner_obj)

        # return Response(res)

    def details(self, request, pk):
        parameters = request.query_params
        lat = parameters.get('lat', None)
        long = parameters.get('long', None)
        from_app = parameters.get('from_app', False)
        queryset = Banner.objects.prefetch_related('banner_location', 'location').filter(enable=True, id=pk)
        banners = Banner.get_all_banners(request, lat, long, from_app, queryset)
        return Response(banners)