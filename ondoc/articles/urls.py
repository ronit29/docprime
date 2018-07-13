from django.urls import path
from .views import upload
urlpatterns = [
    path('articles/upload-image', upload, name='article-image-upload'),
]