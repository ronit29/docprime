from ondoc.articles import models as article_models
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from . import serializers


class ArticleViewSet(viewsets.GenericViewSet):

    queryset = article_models.Article.objects.prefetch_related('category')

    def list(self, request):
        resp = {}
        categories = self.queryset.values_list('category__name', flat=True)
        categories = set(categories)
        for x in categories:
            pass
        return Response({"conditions": categories})

    def retrieve(self, request, pk=None):
        queryset = self.queryset.filter(pk=pk).first()
        serializer = serializers.ArticleRetrieveSerializer(queryset)
        return Response(serializer.data)