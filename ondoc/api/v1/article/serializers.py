from django_comments.models import Comment
from rest_framework import serializers

from fluent_comments.models import FluentComment

from ondoc.articles.models import Article, ArticleLinkedUrl, LinkedArticle
from ondoc.articles.models import ArticleCategory
from ondoc.authentication.models import User
from ondoc.doctor.models import PracticeSpecialization
from ondoc.doctor.v1.serializers import DoctorSerializer, ArticleAuthorSerializer
from django.db import models
from bs4 import BeautifulSoup
import re
from xml.sax.saxutils import unescape


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
    body_doms = serializers.SerializerMethodField()

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

    def get_body_doms(self, obj):
        html_doms = list()
        try:
            object_body = obj.body

            widget_tag_pattern = '<div(?:\s|\w|=|\"|\'|&nbsp;)*class\s*=(?:\s|\"|\')*search-widget(?:\s|\w|=|\"|\'|&nbsp;)*>(?:.*?|\n*?)</div>'
            search_widget_tags = re.findall(widget_tag_pattern, object_body)
            if search_widget_tags:
                html_body = object_body
                counter = 1
                widget_count = len(search_widget_tags)
                for search_widget_tag in search_widget_tags:
                    search_widget_str = str(search_widget_tag)
                    if isinstance(html_body, str):
                        html_body = re.compile(search_widget_str).split(html_body, 1)
                        self.add_html(html_doms, html_body[0], search_widget_tag)
                        if len(html_body) == 2:
                            html_body = html_body[1]
                            if counter == widget_count:
                                self.add_html(html_doms, html_body)
                    counter += 1
            else:
                html_doms.append(self.format_html(obj.body))
        except Exception as e:
            print('Error in body widget format:' + str(e))
            html_doms.clear()
            html_doms.append(self.format_html(obj.body))
        return html_doms

    def format_widget(self, tag):
        search_widget = dict()
        search_widget['type'] = 'search_widget'
        search_widget['content'] = dict()
        soup = BeautifulSoup(tag, 'html.parser')
        widget_tag = soup.find('div')
        widget_tag_attrs = widget_tag.attrs
        if widget_tag_attrs:
            has_specialization = False
            if widget_tag_attrs.get('lat') and widget_tag_attrs.get('lng') and widget_tag_attrs.get('location_name'):
                search_widget['content']['lat'] = widget_tag_attrs.get('lat')
                search_widget['content']['lng'] = widget_tag_attrs.get('lng')
                search_widget['content']['location_name'] = widget_tag_attrs.get('location_name')
            else:
                search_widget['content']['lat'] = None
                search_widget['content']['lng'] = None
                search_widget['content']['location_name'] = None
            if widget_tag_attrs.get('specialization_id'):
                specialization_results = PracticeSpecialization.objects.filter(pk=widget_tag_attrs.get('specialization_id'))
                if specialization_results:
                    has_specialization = True
                    specialization = specialization_results.first()
                    search_widget['content']['specialization_id'] = specialization.id
                    search_widget['content']['specialization_name'] = specialization.name
                else:
                    has_specialization = False
            else:
                has_specialization = False
            if not has_specialization:
                search_widget['content']['specialization_id'] = None
                search_widget['content']['specialization_name'] = None
        return search_widget

    def format_html(self, tag):
        html_tag = dict()
        html_tag['type'] = 'html'
        html_tag['content'] = BeautifulSoup(tag, 'html.parser').prettify()
        return html_tag

    def add_html(self, obj, html_tag, search_widget_tag=False):
        if html_tag:
            obj.append(self.format_html(html_tag))
        if search_widget_tag:
            obj.append(self.format_widget(search_widget_tag))

    class Meta:
        model = Article
        fields = ('title','heading_title', 'url', 'body_doms', 'body', 'icon', 'id', 'seo', 'header_image', 'header_image_alt', 'category',
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

