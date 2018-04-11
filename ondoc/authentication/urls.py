from django.urls import include, path
from . import views

urlpatterns = [
    #path('auth/', views.obtain_auth_token),
    path('otp/generate',views.generate_otp),
    path('otp/verify',views.verify_otp),
    path('register',views.register_user),
]