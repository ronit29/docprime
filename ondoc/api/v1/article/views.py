from ondoc.articles import models as article_models
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from . import serializers


class ArticleViewSet(viewsets.GenericViewSet):

    queryset = article_models.Article.objects.prefetch_related('category')

    def list(self, request):
        resp = []
        categories = self.queryset.values_list('category__name', flat=True)
        categories = list(set(categories))
        for category in categories:
            data = self.queryset.filter(category__name=category)
            if data.exists():
                cat_data = {}
                cat_data['title'] = category
                cat_data['data'] = serializers.ArticleListSerializer(data.all(), many=True, context={'request': request}).data
                resp.append(cat_data)
        return Response(resp)

    def retrieve(self, request, pk=None):
        response = {}
        queryset = self.queryset.filter(pk=pk)
        if queryset.exists():
            serializer = serializers.ArticleRetrieveSerializer(queryset.first(), context={'request': request})
            response = serializer.data
        return Response(response)