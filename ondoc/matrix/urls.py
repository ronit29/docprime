from django.urls import path
from .views import MatrixLead

app_name = 'matrix'
urlpatterns = [
    path('api/v1/matrix/lead/create', MatrixLead.as_view({'post': 'create'}), name='lead-create'),
 ]
