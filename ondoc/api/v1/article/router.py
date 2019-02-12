from django.urls import path
from .views import ArticleViewSet, ArticleCategoryViewSet, TopArticleCategoryViewSet, CommentViewSet

urlpatterns = [
    path('list', ArticleViewSet.as_view({'get': 'list'}), name='article-list'),
    path('category/list', ArticleCategoryViewSet.as_view({'get': 'list'}), name='article-category-list'),
    path('top', TopArticleCategoryViewSet.as_view({'get': 'list'}), name='article-category-list'),
    path('detail', ArticleViewSet.as_view({'get': 'retrieve'}), name='article-details'),
    path('comment/post', CommentViewSet.as_view({'post': 'create'}), name='post-comment'),
    path('comment/list', CommentViewSet.as_view({'get': 'list'}), name='list-comment'),

]
