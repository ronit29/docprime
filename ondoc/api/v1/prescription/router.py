from django.urls import path
from . import views

urlpatterns = [
    path('generate', views.PrescriptionGenerateViewSet.as_view({'post': 'generate'}), name='generate-pdf'),
    path('save_component', views.PrescriptionComponentsViewSet.as_view({'post': 'save_components'}), name='save_components'),
    path('sync_component', views.PrescriptionComponentsViewSet.as_view({'get': 'sync_component'}), name='sync_component'),
]

