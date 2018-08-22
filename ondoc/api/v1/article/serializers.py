from rest_framework import serializers
from ondoc.articles.models import Article
from ondoc.articles.models import ArticleCategory


class ArticleRetrieveSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    class Meta:
        model = Article
        fields = ('title', 'url', 'body', 'icon', 'id', 'description', 'keywords', 'header_image')


class ArticleListSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField
    url = serializers.SerializerMethodField()

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    def get_url(self, obj):
        request = self.context.get('request')
        category = self.context.get('category')
        return request.build_absolute_uri('%s-%s' % (obj.url, category.identifier))\
            if (hasattr(obj, 'url') and hasattr(category, 'identifier')) else None

    class Meta:
        model = Article
        fields = ('title', 'url', 'icon', 'id')


class ArticlePreviewSerializer(serializers.Serializer):
    preview = serializers.BooleanField(required=False)


class ArticleCategoryListSerializer(serializers.ModelSerializer):

    # url = serializers.SerializerMethodField()

    def get_url(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.url) if hasattr(obj, 'url') else None

    class Meta:
        model = ArticleCategory
        fields = ('name', 'url')
