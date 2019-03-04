from django.urls import path
from .views import CartViewSet

urlpatterns = [
    path('add', CartViewSet.as_view({'post': 'add'}), name='add-to-cart'),
    path('all', CartViewSet.as_view({'get': 'list'}), name='list-all-cart'),
    path('process', CartViewSet.as_view({'post': 'process'}), name='process-all-cart'),
    path('remove', CartViewSet.as_view({'post': 'remove'}), name='remove-item'),
]