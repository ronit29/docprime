from django.urls import path
from .views import ArticleViewSet
from .views import ArticleCategoryViewSet

urlpatterns = [
    path('list', ArticleViewSet.as_view({'get': 'list'}), name='article-list'),
    path('category/list', ArticleCategoryViewSet.as_view({'get': 'list'}), name='article-category-list'),
    path('detail/<int:pk>', ArticleViewSet.as_view({'get': 'retrieve'}), name='article-details'),
]
