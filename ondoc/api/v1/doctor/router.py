from django.urls import path
from .views import DoctorAppointmentsViewSet

urlpatterns = [
    
    path('appointment', DoctorAppointmentsViewSet.as_view({'get': 'list'}), name='appointment-list'),
    path('appointment/create', DoctorAppointmentsViewSet.as_view({'post': 'create'}), name='create-appointment'),
    path('appointment/<int:pk>', DoctorAppointmentsViewSet.as_view({'get': 'retrieve'}), name='get-appointment-detail'),
    path('appointment/<int:pk>/update', DoctorAppointmentsViewSet.as_view({'post': 'update'}),
         name='update-appointment-detail'),

#     path('appointment/<int:pk>/update-status',
#          DoctorAppointmentsViewSet.as_view({'post': 'update_status'}), name='update-status'),
 ]
