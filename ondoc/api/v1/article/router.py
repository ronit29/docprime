from django.urls import path
from .views import ArticleViewSet
from .views import ArticleCategoryViewSet
from .views import TopArticleCategoryViewSet

urlpatterns = [
    path('list', ArticleViewSet.as_view({'get': 'list'}), name='article-list'),
    path('category/list', ArticleCategoryViewSet.as_view({'get': 'list'}), name='article-category-list'),
    path('top', TopArticleCategoryViewSet.as_view({'get': 'list'}), name='article-category-list'),
    path('detail', ArticleViewSet.as_view({'get': 'retrieve'}), name='article-details'),
]
