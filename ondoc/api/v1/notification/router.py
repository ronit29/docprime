from django.urls import path
from . import views

urlpatterns = [
    path("appnotifications", views.AppNotificationViewSet.as_view({"get": "list"}),
         name="notifications"),
    path("marknotificationsasviewed",
         views.AppNotificationViewSet.as_view({"post": "mark_notifications_as_viewed"}),
         name="marknotificationsasviewed"),
    path("marknotificationsasread",
         views.AppNotificationViewSet.as_view({"post": "mark_notifications_as_read"}),
         name="marknotificationsasread"),
    path("chat",
         views.ChatNotificationViewSet.as_view({"post": "chat_send"}),
         name="notificationfromchat"),
    path('preview/<str:template_name>',  views.DynamicTemplate.as_view(), name='dynamic-template'),
    path("ipd/emailnotifications", views.IPDIntimateEmailNotificationViewSet.as_view({"get": "send_email_notification"}),
         name="ipd_hospital_email_notifications"),
]
