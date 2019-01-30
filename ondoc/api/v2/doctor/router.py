from django.urls import path
from .views import (DoctorBillingViewSet)

urlpatterns = [
    path('billing_entities', DoctorBillingViewSet.as_view({'get': 'list'}), name='billing_entities'),


]
