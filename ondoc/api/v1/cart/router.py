from django.urls import path
from .views import CartViewSet

urlpatterns = [
    path('create', CartViewSet.as_view({'post': 'create'}), name='create-cart'),
]