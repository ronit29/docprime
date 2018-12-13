from rest_framework import viewsets

from ondoc.banner.models import Banner


class BannerListViewSet(viewsets.GenericViewSet):

    def list(self, request):
        queryset = Banner.objects.all()

