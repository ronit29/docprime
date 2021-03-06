from django.urls import path
from .views import SubscriptionPlanListViewSet, SubscriptionPlanLoggedInUserViewSet

urlpatterns = [
    path('list', SubscriptionPlanListViewSet.as_view({'get': 'list'}), name='subscription_plan_list'),
    path('buy', SubscriptionPlanLoggedInUserViewSet.as_view({'post': 'buy'}), name='subscription_plan_buy'),
    path('retrieve', SubscriptionPlanLoggedInUserViewSet.as_view({'get': 'retrieve'}), name='subscription_plan_retrieve'),
    path('has_plan', SubscriptionPlanLoggedInUserViewSet.as_view({'get': 'has_plan'}), name='subscription_plan_has_a_plan'),
]
