import re
from urllib.parse import urlparse

from django.http import QueryDict
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from ondoc.banner.models import Banner


class BannerListViewSet(viewsets.GenericViewSet):

    def list(self, request):
        banners = Banner.get_all_banners(request)
        return Response(banners)

