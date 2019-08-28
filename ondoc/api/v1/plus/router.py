from django.urls import path
from ondoc.plus.views import (PlusListViewSet)


urlpatterns = [
    path('list', PlusListViewSet.as_view({'get': 'list'}), name='insurance-list'),
]

