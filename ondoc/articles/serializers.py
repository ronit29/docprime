from rest_framework import serializers
from .models import ArticleImage

class ArticleImageSerializer(serializers.Serializer):

    name = serializers.ImageField()
    class Meta:
        model = ArticleImage
        fields = ('name',)

    def create(self, validated_data):
        return ArticleImage.objects.create(**validated_data)
