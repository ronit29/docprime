from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .serializers import ArticleImageSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny

@api_view(['POST'])
def upload(request):
    data = {}
    data['name'] = request.data.get('upload')
    serializer = ArticleImageSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    image = serializer.save()
    return Response({'uploaded':1, 'url':image.name.url})
