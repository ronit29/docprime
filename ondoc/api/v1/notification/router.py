from django.urls import path
from . import views


urlpatterns = [
    path("appnotifications", views.AppNotificationViewSet.as_view({"get": "list"}), name="notifications"),
]