from django.urls import path
from .views import PlusListViewSet, PlusOrderViewSet


urlpatterns = [
    path('list', PlusListViewSet.as_view({'get': 'list'}), name='plus-list'),
    path('lead/create', PlusOrderViewSet.as_view({'post': 'create_plus_lead'}), name='plus-lead-create'),
    # path('create', PlusOrderViewSet.as_view({'post': 'create_order'}), name='plus-subscription-create'),
]

