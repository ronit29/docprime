from ondoc.articles import models as article_models
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from . import serializers
from ondoc.api.pagination import paginate_queryset

class ArticleCategoryViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return article_models.ArticleCategory.objects.all()

    def list(self, request):
        queryset = paginate_queryset(self.get_queryset(), request, 10)
        article_category_list = [serializers.ArticleCategoryListSerializer(category, context={'request': request}).data
                                 for category in queryset]
        return Response(article_category_list)


class ArticleViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return article_models.Article.objects.prefetch_related('category')

    def list(self, request):
        category_url = request.GET.get('categoryUrl', None)
        if not category_url:
            return Response({"error": "Invalid Parameter: categoryUrl"}, status=status.HTTP_400_BAD_REQUEST)

        category_list = article_models.ArticleCategory.objects.filter(url=category_url)
        if not len(category_list) > 0:
            return Response([])

        category = category_list[0]
        articles = category.articles.all()
        article_data = list(filter(lambda article: article.is_published, articles))

        article_data = paginate_queryset(article_data, request, 10)
        resp = serializers.ArticleListSerializer(article_data, many=True,
                                                             context={'request': request, 'category': category}).data
        return Response(resp)

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