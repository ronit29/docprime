from rest_framework import serializers
from ondoc.articles.models import Article
from ondoc.articles.models import ArticleCategory


class ArticleRetrieveSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField()
    seo = serializers.SerializerMethodField()

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.icon.url) if hasattr(obj, 'icon') else None

    def get_seo(self, obj):
        request = self.context.get('request')
        return {'description': obj.description, 'keywords': obj.keywords,
                'image': request.build_absolute_uri(obj.header_image.url), 'title': obj.title}

    class Meta:
        model = Article
        fields = ('title', 'url', 'body', 'icon', 'id', 'seo', 'header_image')


class ArticleListSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.icon.url) if hasattr(obj, 'icon') else None

    def get_url(self, obj):
        return obj.url if hasattr(obj, 'url') else None

    class Meta:
        model = Article
        fields = ('title', 'url', 'icon', 'header_image')


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
