from ondoc.articles import models as article_models
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from ondoc.articles.models import ArticleCategory
from . import serializers
from ondoc.api.pagination import paginate_queryset
from django.db import transaction


class ArticleCategoryViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return article_models.ArticleCategory.objects.all()

    @transaction.non_atomic_requests
    def list(self, request):
        queryset = paginate_queryset(self.get_queryset(), request, 10)
        article_category_list = [serializers.ArticleCategoryListSerializer(category, context={'request': request}).data
                                 for category in queryset]
        return Response(article_category_list)


class TopArticleCategoryViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return article_models.ArticleCategory.objects.all()

    @transaction.non_atomic_requests
    def list(self, request):
        response = list()
        for category in self.get_queryset():
            article_list = category.articles.filter(is_published=True).order_by('id')[:8]
            resp = serializers.ArticleListSerializer(article_list, many=True,
                                                     context={'request': request}).data
            category_serialized = serializers.ArticleCategoryListSerializer(category, context={'request': request}).data
            response.append({'articles': resp, 'name': category_serialized['name'], 'url': category_serialized['url'],
                             'title': category_serialized['title'], 'description': category_serialized['description']})
        return Response(response)


class ArticleViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return article_models.Article.objects.prefetch_related('category').filter(is_published=True)

    @transaction.non_atomic_requests
    def list(self, request):
        category_url = request.GET.get('categoryUrl', None)
        if not category_url:
            return Response({"error": "Missing Parameter: categoryUrl"}, status=status.HTTP_400_BAD_REQUEST)

        article_start = request.GET.get('startsWith', None)
        article_contains = request.GET.get('contains', None)
        article_data = self.get_queryset().filter(category__url=category_url)
        if article_start:
            article_data = article_data.filter(title__istartswith=article_start)
        if article_contains and len(article_contains) > 2:
            article_data = article_data.filter(title__icontains=article_contains)
        article_data = paginate_queryset(article_data, request, 10)
        resp = serializers.ArticleListSerializer(article_data, many=True,
                                                 context={'request': request}).data
        title = ''
        description = ''
        title_description = ArticleCategory.objects.filter(url=category_url).values('title', 'description')
        if title_description.exists():
            title = title_description.first().get('title', '')
            description = title_description.first().get('description', '')

        category_seo = {
            "title": title,
            "description": description
        }

        return Response({'result': resp, 'seo': category_seo})

    @transaction.non_atomic_requests
    def retrieve(self, request):
        serializer = serializers.ArticlePreviewSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        preview = serializer.validated_data.get('preview')
        article_url = serializer.validated_data.get('url')
        queryset = self.get_queryset().filter(url=article_url)
        if not preview:
            queryset = queryset.filter(is_published=True)
        if queryset.exists():
            serializer = serializers.ArticleRetrieveSerializer(queryset.first(), context={'request': request})
            response = serializer.data
            return Response(response)
        else:
            return Response({"error": "Not Found"}, status=status.HTTP_404_NOT_FOUND)