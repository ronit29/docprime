from collections import defaultdict

from django.db.models import F

from ondoc.common.models import MatrixMappedCity
from ondoc.common.models import MatrixMappedState
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment
from ondoc.common.models import SyncBookingAnalytics
from ondoc.corporate_booking.models import CorporateDeal
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from datetime import datetime
from django.conf import settings

from fluent_comments.models import FluentComment

from ondoc.api.v1.article.serializers import CommentAuthorSerializer, CommentSerializer
from ondoc.comments.models import CustomComment
from ondoc.seo.models import NewDynamic
# from .serializers import CommentSerializer
from ondoc.articles import models as article_models
from ondoc.articles.models import ArticleCategory, Article
from . import serializers
from ondoc.api.pagination import paginate_queryset
from ondoc.authentication.models import User
from ondoc.api.v1.utils import RawSql
import logging
logger = logging.getLogger(__name__)


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
        articles_count = article_data.count()
        article_data = paginate_queryset(article_data, request, 50)
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

        dynamic_content = NewDynamic.objects.filter(url__url=category_url, is_enabled=True).first()
        top_content = None
        bottom_content = None
        if dynamic_content:
            top_content = dynamic_content.top_content
            bottom_content = dynamic_content.bottom_content
        return Response(
            {'result': resp, 'seo': category_seo, 'category': category.name, 'total_articles': articles_count, 'search_content': top_content
             , 'bottom_content': bottom_content})

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
            user_name = data['name']
            user_email = data['email']

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
                return Response(status=status.HTTP_404_NOT_FOUND, data={'error': 'article not found'})
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
            return Response(status=status.HTTP_404_NOT_FOUND, data={'error': 'comment not found'})

    def list(self, request):
        data = request.GET
        article = data.get('article')
        article = article_models.Article.objects.filter(id=article).first()
        if article:
            comments = self.queryset.filter(object_pk=article.id)

            serializer = CommentSerializer(comments, many=True, context={'request': request})
            return Response(serializer.data)


class OptimusViewSet(viewsets.GenericViewSet):

    def get_analytics_data(self, request, *args, **kwargs):
        data = dict()
        data['matrix_mapped_city'] = list()
        data['matrix_mapped_state'] = list()
        data['opd_appointment'] = list()
        data['lab_appointment'] = list()
        data['corporate_deals'] = list()

        cities = MatrixMappedCity.objects.filter(synced_analytics__isnull=True)[0:10]
        for city in cities:
            analytics_data = city.get_booking_analytics_data()
            data['matrix_mapped_city'].append(analytics_data)

        states = MatrixMappedState.objects.filter(synced_analytics__isnull=True)[0:10]
        for state in states:
            analytics_data = state.get_booking_analytics_data()
            data['matrix_mapped_state'].append(analytics_data)

        opd_apps = OpdAppointment.objects.filter(synced_analytics__isnull=True)[0:10]
        for app in opd_apps:
            analytics_data = app.get_booking_analytics_data()
            data['opd_appointment'].append(analytics_data)

        lab_apps = LabAppointment.objects.filter(synced_analytics__isnull=True)[0:10]
        for app in lab_apps:
            analytics_data = app.get_booking_analytics_data()
            data['lab_appointment'].append(analytics_data)
            # print('lab-id : {} has been synced'.format(app.id))

        corp_deals = CorporateDeal.objects.filter(synced_analytics__isnull=True)[0:10]
        for deal in corp_deals:
            analytics_data = deal.get_booking_analytics_data()
            data['corporate_deals'].append(analytics_data)

        to_be_updated = SyncBookingAnalytics.objects.exclude(synced_at=F('last_updated_at'))[0:10]
        for obj in to_be_updated:
            row = obj.content_object

            if row.__class__.__name__ == 'OpdAppointment':
                analytics_data = row.sync_with_booking_analytics()
                data['opd_appointment'].append(analytics_data)
            elif row.__class__.__name__ == 'LabAppointment':
                analytics_data = row.sync_with_booking_analytics()
                data['lab_appointment'].append(analytics_data)
            elif row.__class__.__name__ == 'CorporateDeal':
                analytics_data = row.sync_with_booking_analytics()
                data['corporate_deals'].append(analytics_data)
            elif row.__class__.__name__ == 'MatrixMappedCity':
                analytics_data = row.sync_with_booking_analytics()
                data['matrix_mapped_city'].append(analytics_data)
            elif row.__class__.__name__ == 'MatrixMappedState':
                analytics_data = row.sync_with_booking_analytics()
                data['matrix_mapped_state'].append(analytics_data)

        return Response(data=data)
