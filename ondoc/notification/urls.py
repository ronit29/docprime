from django.urls import include, path

from . import views

#from rest_framework.authtoken import views

app_name="notification"
urlpatterns = [
    # path('auth/', views.obtain_auth_token),
    path('notification/preview/<str:template_name>', views.DynamicTemplate.as_view(), name='dynamic-template'),
]
