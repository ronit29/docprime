from django.urls import path
from .views import SubscriptionPlanListViewSet

urlpatterns = [
    path('list', SubscriptionPlanListViewSet.as_view({'get': 'list'}), name='subscription_plan_list'),
]