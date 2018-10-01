from django.urls import path
from .views import EventCreateViewSet, ServerHitMonitor

urlpatterns = [
    path('event/save', EventCreateViewSet.as_view({'post': 'create'}), name='event-create'),
    path('serverhit', ServerHitMonitor.as_view({'post': 'create'}), name='server-hit-create')
]