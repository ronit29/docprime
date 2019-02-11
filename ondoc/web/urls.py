from django.urls import path
from django.conf.urls import url
from . import views


app_name = 'web'
urlpatterns = [
    path('', views.index, name='index'),
    # url(r'^careers/', views.careers_page, name='careers_page'),
    # url(r'^privacy/', views.privacy_page, name='privacy_page'),
    # url(r'^terms/', views.terms_page, name='terms_page'),
    # url(r'^news-and-media/', views.media_page, name='media_page'),
    # url(r'^aboutus/', views.about_page, name='about_page'),
    # url(r'^contactus/', views.contact_page, name='contact_page'),
    # url(r'^disclaimer/', views.disclaimer_page, name='disclaimer_page'),
    # url(r'^howitworks/', views.howitworks_page, name='howitworks_page'),
    url(r'^admin/agent/doctor', views.doctor_login_via_agent, name='agent_doctor_page'),
    url(r'^admin/agent/', views.user_appointment_via_agent, name='agent_page'),
    url(r'^admin/search-data/', views.upload_search_data, name='search_data'),
    url(r'^short/(?P<hash>[a-zA-Z0-9]+)', views.redirect_to_original_url, name='redirect-original-url'),
    url(r'^page/redirect-to-app', views.redirect_to_app, name='redirect-to-app'),
]
