from django.urls import path
from . import views

urlpatterns = [
    path('manageable_labs', views.ManageableLabsViewSet.as_view({'get': 'list'}), name='manageable_labs'),
]


