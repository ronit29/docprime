from django_comments.models import Comment
from rest_framework import serializers

from fluent_comments.models import FluentComment

from ondoc.articles.models import Article, ArticleLinkedUrl, LinkedArticle
from ondoc.articles.models import ArticleCategory
from ondoc.authentication.models import User
from ondoc.doctor.v1.serializers import DoctorSerializer, ArticleAuthorSerializer
from django.db import models


class LinkedArticleSerializer(serializers.ModelSerializer):

    url = serializers.SerializerMethodField()

    class Meta:
        model = LinkedArticle
        fields = ('title', 'url')

    def get_url(self, obj):
        return obj.linked_article.url


class LinkedUrlSerializer(serializers.ModelSerializer):

    class Meta:
        model = ArticleLinkedUrl
        fields = ('url', 'title')


class ArticleRetrieveSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField()
    seo = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    # linked_urls = serializers.SerializerMethodField()
    # linked_articles = serializers.SerializerMethodField()
    published_date = serializers.SerializerMethodField()
    linked = serializers.SerializerMethodField()
    author = ArticleAuthorSerializer()
    last_updated_at = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    def get_comments(self, obj):
        comments = FluentComment.objects.filter(object_pk=str(obj.id), parent_id=None, is_public=True)
        serializer = CommentSerializer(comments, many=True, context={'request': self.context.get('request')})
        return serializer.data

    def get_linked(self, obj):
        resp = {}
        for la in obj.related_articles.all():
            if la.content_box:
                if not resp.get(la.content_box.pk):
                    resp[la.content_box.pk] = {'content_box_title': la.content_box.title, 'urls': []}
                resp[la.content_box.pk]['urls'].append({'title': la.title, 'url': la.linked_article.url})

        for lu in obj.articlelinkedurl_set.all():
            if lu.content_box:
                if not resp.get(lu.content_box.pk):
                    resp[lu.content_box.pk] = {'content_box_title': lu.content_box.title, 'urls': []}
                resp[lu.content_box.pk]['urls'].append({'title': lu.title, 'url': lu.url})


        final_result = []
        for key, value in resp.items():
            final_result.append(value)
        return final_result

    # def get_linked_urls(self, obj):
    #     serializer = LinkedUrlSerializer(obj.articlelinkedurl_set.all(), many=True)
    #     return serializer.data
    #
    # def get_linked_articles(self, obj):
    #     serializer = LinkedArticleSerializer(obj.related_articles.all(), many=True)
    #     return serializer.data

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.icon.url) if hasattr(obj, 'icon') and obj.icon.name else None

    def get_seo(self, obj):
        request = self.context.get('request')
        return {'description': obj.description, 'keywords': obj.keywords,
                'image': request.build_absolute_uri(obj.header_image.url)
                if hasattr(obj, 'header_image') and obj.header_image.name else None, 'title': obj.title}

    def get_category(self, obj):
        return {'name': obj.category.name, 'url': obj.category.url}

    def get_published_date(self, obj):
        return '{:%d-%m-%Y}'.format(obj.published_date) if obj.published_date else None

    def get_last_updated_at(self, obj):
        return '{:%d-%m-%Y}'.format(obj.updated_at)

    class Meta:
        model = Article
        fields = ('title','heading_title', 'url', 'body', 'icon', 'id', 'seo', 'header_image', 'header_image_alt', 'category',
                  'linked', 'author_name', 'published_date', 'author', 'last_updated_at', 'comments')


class ArticleListSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    articleTeaser = serializers.SerializerMethodField()

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.icon.url) if hasattr(obj, 'icon') and obj.icon.name else None

    def get_url(self, obj):
        return obj.url if hasattr(obj, 'url') else None

    def get_articleTeaser(self, obj):
        import re
        value = re.sub(r'<h.*?>.*?</h.*?>|<ol>.*?</ol>|<ul>.*?<ul>|<img.*?>', '', obj.body)
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', value)
        # chunks = cleantext.split(" ")
        value = "".join(cleantext[:200])
        value = value.replace('&nbsp;', '')
        if len(cleantext) > 200:
            value += " ..."
        return value

    class Meta:
        model = Article
        fields = ('title', 'url', 'icon', 'header_image', 'header_image_alt', 'articleTeaser', 'id')


class ArticlePreviewSerializer(serializers.Serializer):
    preview = serializers.BooleanField(required=False)
    url = serializers.CharField(required=True)

    def validate(self, data):
        return data


class ArticleCategoryListSerializer(serializers.ModelSerializer):

    # url = serializers.SerializerMethodField()

    def get_url(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.url) if hasattr(obj, 'url') else None

    class Meta:
        model = ArticleCategory
        fields = ('name', 'url', 'title', 'description')


class FilteredCommentsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_public=True)



# class RecursiveField(serializers.Serializer):
#     def to_representation(self, value):
#         #value.children = value.children.filter('is_public')
#         value.filter_children = value.children.filter(is_public=True)
#         if value.is_public == True:
#             serializer = self.parent.parent.__class__(
#                 value,
#                 context=self.context)
#             return serializer.data


class CommentSerializer(serializers.ModelSerializer):
    #children = RecursiveField(many=True)
    children = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    profile_img = serializers.SerializerMethodField()

    def get_profile_img(self, obj):
        profile_image = None

        user = obj.user
        if user and user.user_type == User.CONSUMER:
            profile = user.profiles.filter(is_default_user=True).first()
            if profile:
                profile_image = profile.get_thumbnail()

        #if not profile image

        return profile_image

    def get_children(self, obj):
        if len(obj.children.filter(is_public=True))>0:
            return CommentSerializer(obj.children.filter(is_public=True), many=True).data
        return None

    def get_author(self, obj):
        custom_data = obj.customcomment_set.first()
        if custom_data and custom_data.author:
            return ArticleAuthorSerializer(obj.content_object.author).data
        return None

    class Meta:
        model = FluentComment
        fields = (
            'id',
            'comment',
            'children',
            'submit_date',
            'user_name',
            'author',
            'profile_img',
           )


class CommentAuthorSerializer(serializers.ModelSerializer):
    author = ArticleAuthorSerializer()

    class Meta:
        model = Article
        fields = ('author',)

