from django.urls import include, path

from . import views, doctoronboard_view
from . import upload

#from rest_framework.authtoken import views

app_name="onboard"
urlpatterns = [
    # path('auth/', views.obtain_auth_token),
    path('lab', views.LabOnboard.as_view(), name='lab'),
    path('doctor', views.DoctorOnboard.as_view(), name='doctor'),
    path('doctor/otp', doctoronboard_view.otp, name='doctor_otp'),
    # path('lab', views.lab, name='lab'),
    path('otp', views.otp, name='otp'),
    # path('doctor', views.lab, name='doctor'),
    path('generate-url', views.generate, name='generate-url'),
    path('generate-doctor-url', views.generate_doctor, name='generate-doctor-url'),
    path('upload', upload.BasicUploadView.as_view(), name='basic_upload'),
    path('doctor-upload', upload.DoctorUploadView.as_view(), name='doctor_upload'),
    path('terms', views.terms, name='terms'),
]