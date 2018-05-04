from django.urls import path
from .views import PathologyTestList

urlpatterns = [

    path('test/', PathologyTestList.as_view({'get': 'list'}), name='test-list'),
    path('test/<int:id>/', PathologyTestList.as_view({'get': 'retrieve'}), name='test-detail'),
]
