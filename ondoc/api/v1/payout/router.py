from django.urls import path
from . import views


urlpatterns = [
    path("billing/current", views.BillingViewSet.as_view({"get": "current_billing"}), name="billing-current"),
    path("billing", views.BillingViewSet.as_view({"get": "list"}), name="billing")
]