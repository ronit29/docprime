from django.urls import path

from .views import MaskNumberViewSet

urlpatterns = [
    path('mask-number', MaskNumberViewSet.as_view({'post':'mask_number'}), name ='mask_number')
]
