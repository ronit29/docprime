from django.urls import path
from .views import PlusListViewSet, PlusOrderViewSet, PlusOrderLeadViewSet, PlusProfileViewSet, PlusDataViewSet, PlusIntegrationViewSet


urlpatterns = [
    path('list', PlusListViewSet.as_view({'get': 'list'}), name='plus-list'),
    path('lead/create', PlusOrderLeadViewSet.as_view({'post': 'create_plus_lead'}), name='plus-lead-create'),
    path('create', PlusOrderViewSet.as_view({'post': 'create_order'}), name='plus-subscription-create'),
    path('dashboard', PlusProfileViewSet.as_view({'get': 'dashboard'}), name='dashboard'),
    path('add/members', PlusOrderViewSet.as_view({'post': 'add_members'}), name='plus-subscription-add-members'),
    path('push_dummy_data', PlusDataViewSet.as_view({'post': 'push_dummy_data'}), name='push-dummy-data'),
    path('show_dummy_data', PlusDataViewSet.as_view({'get': 'show_dummy_data'}), name='show-dummy-data'),
    path('push_vip_lead', PlusIntegrationViewSet.as_view({'post': 'push_vip_integration_leads'}), name='push_vip_integration_leads'),

]

