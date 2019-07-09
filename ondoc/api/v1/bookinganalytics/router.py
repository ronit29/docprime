from django.urls import path
from .views import OptimusViewSet

urlpatterns = [
    path('get-analytics-data', OptimusViewSet.as_view({'get': 'get_analytics_data'}), name='analytics-data')
]
