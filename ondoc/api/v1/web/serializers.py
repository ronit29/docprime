from rest_framework import serializers


class TinyUrlSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=5000)