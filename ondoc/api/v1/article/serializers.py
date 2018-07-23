from rest_framework import serializers
from ondoc.articles.models import Article


class ArticleRetrieveSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    class Meta:
        model = Article
        fields = ('title', 'url', 'body', 'icon', 'id')


class ArticleListSerializer(serializers.ModelSerializer):

    icon = serializers.SerializerMethodField

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    class Meta:
        model = Article
        fields = ('title', 'url', 'icon', 'id')
