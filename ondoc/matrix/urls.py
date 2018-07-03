from django.urls import path
from .views import MatrixLead

app_name = 'matrix'
urlpatterns = [
    path('lead_create', MatrixLead.as_view({'post': 'create'}), name='lead-create'),
 ]
