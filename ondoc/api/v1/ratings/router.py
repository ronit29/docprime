from django.urls import path
from .views import RatingsViewSet, AppRatingsViewSet, ListRatingViewSet
from .views import GetComplementViewSet

urlpatterns = [
    path('create', RatingsViewSet.as_view({'post': 'create'}), name='submit-rating'),
    path('app/create', AppRatingsViewSet.as_view({'post': 'create'}), name='createapp-rating'),
    path('list', ListRatingViewSet.as_view({'get': 'list'}), name='get-ratings'),
    path('prompt/close', RatingsViewSet.as_view({'post': 'prompt_close'}), name='prompt_close'),
    path('unrated', RatingsViewSet.as_view({'get': 'unrated'}), name='unrated'),
    path('retrieve/<int:pk>', RatingsViewSet.as_view({'get': 'retrieve'}), name='get-ratings'),
    path('update/<int:pk>', RatingsViewSet.as_view({'post' : 'update'}), name='update-rating'),
    path('compliments', GetComplementViewSet.as_view({'get': 'get_complements'}), name='get-complements'),
]

