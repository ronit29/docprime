from collections import defaultdict
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from datetime import datetime
from django.conf import settings

from fluent_comments.models import FluentComment

from ondoc.api.v1.article.serializers import CommentAuthorSerializer
from ondoc.comments.models import CustomComment
from ondoc.seo.models import NewDynamic
from .serializers import CommentSerializer
from ondoc.articles import models as article_models
from ondoc.articles.models import ArticleCategory, Article
from . import serializers
from ondoc.api.pagination import paginate_queryset
from ondoc.authentication.models import User
from ondoc.api.v1.utils import RawSql


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
        return article_models.Article.objects.prefetch_related('category', 'author').filter(is_published=True)

    @transaction.non_atomic_requests
    def list(self, request):
        category_url = request.GET.get('categoryUrl', None)
        if not category_url:
            return Response({"error": "Missing Parameter: categoryUrl"}, status=status.HTTP_400_BAD_REQUEST)

        article_start = request.GET.get('startsWith', None)
        article_contains = request.GET.get('contains', None)
        recent_articles = None
        recent_articles_data = None
        recent_articles_dict = None

        title_description = ArticleCategory.objects.filter(url=category_url).values('title', 'description', 'name')

        category_qs = article_models.ArticleCategory.objects.filter(url=category_url)
        if category_qs.exists():
            category = category_qs.first()
        else:
            return Response(status=status.HTTP_404_NOT_FOUND, data={'error': 'Category url not found'})

        article_data = self.get_queryset().filter(category__url=category_url)
        if article_start:
            article_data = article_data.filter(title__istartswith=article_start)
        if article_contains and len(article_contains) > 2:
            article_data = article_data.filter(title__icontains=article_contains)

        if title_description and title_description.first().get('name') and title_description.first().get('name').lower() == 'Medicines'.lower():
            recent_articles_data = article_data.filter(is_published=True).order_by('-updated_at')[:10]

        recent_articles = serializers.ArticleListSerializer(recent_articles_data, many=True,
                                                            context={'request': request}).data
        recent_articles_dict = {'title': 'Recent Articles', 'items': recent_articles}

        articles_count = article_data.count()
        article_data = paginate_queryset(article_data, request, 50)
        resp = serializers.ArticleListSerializer(article_data, many=True,
                                                 context={'request': request}).data

        title = ''
        description = ''

        if title_description.exists():
            title = title_description.first().get('title', '')
            description = title_description.first().get('description', '')

        category_seo = {
            "title": title,
            "description": description
        }

        dynamic_content = NewDynamic.objects.filter(url__url=category_url, is_enabled=True).first()
        top_content = None
        bottom_content = None

        if dynamic_content:
            top_content = dynamic_content.top_content
            bottom_content = dynamic_content.bottom_content

        return Response(
            {'result': resp, 'seo': category_seo, 'category': category.name, 'total_articles': articles_count, 'search_content': top_content
             , 'bottom_content': bottom_content, 'recent_articles': recent_articles_dict})

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


class CommentViewSet(viewsets.ModelViewSet):
    queryset = FluentComment.objects.filter(is_public=True)
    serializer_class = CommentSerializer

    def create(self, request, *args, **kwargs):
        user = None
        if request.user.is_authenticated:
            user = request.user

        data = self.request.data
        #user = self.request.user
        parent_id = None
        comment = data['comment']
        if comment:
            user_email = data['email']
            try:
                validate_email(user_email)
            except ValidationError as e:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': format(e.messages[0])})
            user_name = data['name']

            article_id = data['article']

            if user and user.user_type == User.CONSUMER:
                user_name = user.full_name
                user_email = user.get_default_email

            if not user_name:
                user_name = 'Anonymous'

            if 'parent' in data:
                parent_id = data['parent']

            # article_parent_obj = Article.objects.filter(id=parent).first()
            # if article_parent_obj:
            #     parent = article_parent_obj
            parent = None
            article = None
            if parent_id:
                parent = FluentComment.objects.filter(id=parent_id).first()
            if parent:
                article = parent.content_object
                    #Article.objects.filter(id=parent.object_pk).first()
            elif article_id:
                article = Article.objects.filter(id=article_id).first()
            if not article:
                return Response(status=status.HTTP_404_NOT_FOUND, data={'error': 'Article not found.'})
                ##raise error

            submit_date = datetime.now()
            content_type = ContentType.objects.get(model="article").pk
            comment = FluentComment.objects.create(object_pk=article.id,
                                   comment=comment,
                                   content_type_id=content_type,
                                   site_id=settings.SITE_ID, parent_id=parent.id if parent else None, user_name=user_name,
                                   user_email=user_email, user=user, is_public=False)

            # if parent:
            #     article_id = parent
            # elif article:
            #     article_id = article
            #
            # if article or parent:
            #     article_obj = Article.objects.filter(id=article_id).first()
            #     custom_comment = CustomComment.objects.create(author=article_obj.author, comment=comment)

            serializer = CommentSerializer(comment, context={'request': request})

            response = {}
            response['status'] = 1
            response['message'] = 'Comment posted successfully'
            response['comment'] = serializer.data

            return Response(response)

        else:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'Comment not found.'})

    def list(self, request):
        data = request.GET
        article = data.get('article')
        article = article_models.Article.objects.filter(id=article).first()
        if article:
            comments = self.queryset.filter(object_pk=article.id)

            serializer = CommentSerializer(comments, many=True, context={'request': request})
            return Response(serializer.data)





