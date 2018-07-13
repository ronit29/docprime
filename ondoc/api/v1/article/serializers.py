from rest_framework import serializers
from ondoc.articles.models import Article



class ArticleListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Article
        fields = ('title', 'url', 'body')

class ArticleRetrieveSerializer(serializers.ModelSerializer):

    class Meta:
        model = Article
        fields = ('title', 'url', 'body')
