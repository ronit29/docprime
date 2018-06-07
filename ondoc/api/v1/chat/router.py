from django.urls import path
from .views import ChatSearchedItemsViewSet

urlpatterns = [
    path('chatsearcheditems', ChatSearchedItemsViewSet.as_view({'get': 'list'}), name='searched-items'),
]
