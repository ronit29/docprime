from ondoc.articles import models as article_models
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from . import serializers


class ArticleCategoryViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return article_models.ArticleCategory.objects.all()

    def list(self, request):
        article_category_list = [serializers.ArticleCategoryListSerializer(category, context={'request': request}).data
                                 for category in self.get_queryset()]
        return Response(article_category_list)


class ArticleViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return article_models.Article.objects.prefetch_related('category')

    def list(self, request):
        category_url = request.GET.get('categoryUrl', None)
        resp = []
        if not category_url:
            return Response([])
        categories = article_models.ArticleCategory.objects.filter(url=category_url).prefetch_related('articles').distinct()
        for category in categories.all():
            if category.articles:
                article_data = []
                for article in category.articles.all():
                    if article.is_published:
                        article_data.append(article)
                cat_data = {}
                if article_data:
                    cat_data['title'] = category.name
                    cat_data['data'] = serializers.ArticleListSerializer(article_data, many=True,
                                                                 context={'request': request, 'category': category}).data
                    resp.append(cat_data)
        return Response(resp)

    def retrieve(self, request, pk=None):
        response = {}
        queryset = self.get_queryset().filter(pk=pk)
        serializer = serializers.ArticlePreviewSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        preview = serializer.validated_data.get('preview')
        if not preview:
            queryset = queryset.filter(is_published=True)
        if queryset.exists():
            serializer = serializers.ArticleRetrieveSerializer(queryset.first(), context={'request': request})
            response = serializer.data
            return Response(response)
        else:
            return Response({"error": "Not Found"}, status=status.HTTP_404_NOT_FOUND)