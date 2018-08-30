from django.urls import path
from .views import TinyUrlViewset

urlpatterns = [
    path('createurl', TinyUrlViewset.as_view({'post': 'create_url'}), name='create-url')
]