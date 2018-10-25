from django.urls import path

urlpatterns = [
    path('list', ProcedureListViewSet.as_view({'list': 'list'}), name='procedure-list'),
]