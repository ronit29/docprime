from django.urls import path
from .views import ScreenViewSet

urlpatterns = [
    path('home-page', ScreenViewSet.as_view({'get': 'home_page'}), name='home-page'),
]