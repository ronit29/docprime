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
        lat = parameters.get('lat', '28.450367')
        long = parameters.get('long', '77.071848')
        banners = Banner.get_all_banners(request)
        res = []
        for banner_obj in banners:
            if banner_obj.get('latitude') and banner_obj.get('longitude') and banner_obj.get('radius'):
                latitude = banner_obj.get('latitude')
                longitude = banner_obj.get('longitude')
                radius = banner_obj.get('radius') * 1000  # Radius in metres
                pnt1 = Point(float(longitude), float(latitude))
                if lat and long:
                    try:
                        pnt2 = Point(float(long), float(lat))
                    except:
                        return Response({'msg': 'Invalid Lat Long'}, status=status.HTTP_400_BAD_REQUEST)

                    distance = pnt1.distance(pnt2)*100  # Distance in metres
                    if distance > radius:

                        continue

                    else:

                        res.append(banner_obj)
            else:
                res.append(banner_obj)

        return Response(res)

