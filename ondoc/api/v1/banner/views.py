import re
from urllib.parse import urlparse

from django.contrib.gis.geos import Point
from django.http import QueryDict
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from ondoc.banner.models import Banner


class BannerListViewSet(viewsets.GenericViewSet):

    def list(self, request):
        parameters = request.query_params
        lat = parameters.get('lat', None)
        long = parameters.get('long', None)
        final_result = None
        banners = Banner.get_all_banners(request)
        res1 = []
        res2 = []
        for banner_obj in banners:
            if lat and long:
                if banner_obj.get('latitude') and banner_obj.get('longitude') and banner_obj.get('radius'):
                    latitude = banner_obj.get('latitude')
                    longitude = banner_obj.get('longitude')
                    radius = banner_obj.get('radius') * 1000  # Radius in metres
                    pnt1 = Point(float(longitude), float(latitude))
                    try:
                        pnt2 = Point(float(long), float(lat))
                    except:
                        return Response({'msg': 'Invalid Lat Long'}, status=status.HTTP_400_BAD_REQUEST)

                    distance = pnt1.distance(pnt2)*100  # Distance in metres
                    if distance > radius:

                        continue

                    else:
                        res1.append(banner_obj)

                else:
                    res2.append(banner_obj)

            elif (banner_obj.get('latitude') and banner_obj.get('longitude') and banner_obj.get('radius')) or \
                    (banner_obj.get('latitude') and banner_obj.get('longitude') and banner_obj.get('radius') == 0):
                res1.append(banner_obj)

            else:
                res2.append(banner_obj)

        return Response({'location_banners': res1, 'non_location_banners': res2})

