from rest_framework import serializers
from ondoc.articles.models import Article, ArticleLinkedUrl
from ondoc.articles.models import ArticleCategory


class LinkedArticleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Article
        fields = ('url', 'title')


class LinkedUrlSerializer(serializers.ModelSerializer):

    class Meta:
        model = ArticleLinkedUrl
        fields = ('url', 'title')


class ArticleRetrieveSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField()
    seo = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    linked_urls = serializers.SerializerMethodField()
    linked_articles = serializers.SerializerMethodField()
    published_date = serializers.SerializerMethodField()

    def get_linked_urls(self, obj):
        serializer = LinkedUrlSerializer(obj.articlelinkedurl_set.all(), many=True)
        return serializer.data

    def get_linked_articles(self, obj):
        serializer = LinkedArticleSerializer(obj.linked_articles.filter(is_published=True), many=True)
        return serializer.data

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

    class Meta:
        model = Article
        fields = ('title', 'url', 'body', 'icon', 'id', 'seo', 'header_image', 'header_image_alt', 'category',
                  'linked_urls', 'linked_articles', 'author_name', 'published_date')


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
        chunks = cleantext.split(" ")
        value = " ".join(chunks[:100])
        value = value.replace('&nbsp;', '')
        return value

    class Meta:
        model = Article
        fields = ('title', 'url', 'icon', 'header_image', 'header_image_alt', 'articleTeaser')


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
        fields = ('name', 'url')
