from django.urls import path
from .views import EventCreateViewSet

urlpatterns = [
    path('event/save', EventCreateViewSet.as_view({'post': 'create'}), name='event-create')
]