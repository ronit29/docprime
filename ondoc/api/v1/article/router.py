from django.urls import path
from .views import ArticleViewSet

urlpatterns = [
    path('list', ArticleViewSet.as_view({'get': 'list'}), name='article-list'),
    path('detail/<int:pk>', ArticleViewSet.as_view({'get': 'retrieve'}), name='article-details'),
]
