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


class BannerListViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)

    def get_queryset(self):
        return None

    def list(self, request):
        parameters = request.query_params
        lat = parameters.get('lat', None)
        long = parameters.get('long', None)
        from_app = parameters.get('from_app', False)
        banners = Banner.get_all_banners(request, lat, long, from_app)
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

