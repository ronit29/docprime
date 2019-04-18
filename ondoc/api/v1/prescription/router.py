from django.urls import path
from . import views

urlpatterns = [
    path('generate', views.PrescriptionGenerateViewSet.as_view({'post': 'generate'}), name='generate-pdf'),
]

