from django.urls import path
from .views import CitiesViewSet, PdfViewSet

urlpatterns = [
    path('cities/list', CitiesViewSet.as_view({'get': 'list'}), name='cities-list'),
    path('generate/pdf', PdfViewSet.as_view({'post': 'generate'},), name='generate-pdf'),
]
