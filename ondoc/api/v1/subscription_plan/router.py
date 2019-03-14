from django.urls import path
from .views import SubscriptionPlanListViewSet, SubscriptionPlanLoggedInUserViewSet

urlpatterns = [
    path('list', SubscriptionPlanListViewSet.as_view({'get': 'list'}), name='subscription_plan_list'),
    path('buy', SubscriptionPlanLoggedInUserViewSet.as_view({'get': 'buy'}), name='subscription_plan_buy'),
]
