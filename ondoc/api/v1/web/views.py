from ondoc.web import models as web_models
from .serializers import TinyUrlSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import GenericViewSet
import random
import string


class TinyUrlViewset(GenericViewSet):

    def create_url(self, request):
        serializer = TinyUrlSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = request.data
        original_url = data.get('url')
        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(10)])
        tiny_url = web_models.TinyUrl.objects.filter(short_code=random_string).first()
        if tiny_url:
            return Response({}, status=status.HTTP_400_BAD_REQUEST)
        tiny_url = web_models.TinyUrl.objects.create(original_url=original_url, short_code=random_string)
        return Response({'tiny_url': tiny_url.get_tiny_url()})



