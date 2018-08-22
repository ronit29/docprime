from django.urls import path
from .views import userlogin_via_agent


urlpatterns = [
    path('agent/user/appointment', userlogin_via_agent, name='agent-login')
]
