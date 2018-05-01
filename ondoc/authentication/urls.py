from django.urls import include, path
from . import views

urlpatterns = [
    #path('auth/', views.obtain_auth_token),
    path('otp/generate',views.generate_otp),
    path('otp/user',views.login_user),
    path('otp/doctor',views.login_doctor),
    path('register',views.register_user),
    path('logout',views.logout)
]