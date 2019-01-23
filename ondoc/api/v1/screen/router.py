from django.urls import path
from .views import ScreenViewSet

urlpatterns = [
    path('/', ScreenViewSet.as_view({'get': 'list'}), name='screen'),
]