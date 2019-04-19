from django.urls import path

from .views import MaskNumberViewSet, IvrViewSet

urlpatterns = [
    path('mask-number', MaskNumberViewSet.as_view({'post':'mask_number'}), name='mask_number'),
    path('ivr-response/update', IvrViewSet.as_view({'post':'update'}), name='ivr_udpate')
]
