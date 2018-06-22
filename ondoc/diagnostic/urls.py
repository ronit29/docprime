from django.conf.urls import url, include
from django.urls import path
from . import views
from .api.v1.router import urlpatterns as v1

app_name = 'diagnostic'

urlpatterns = [
    # path('v1/', include(v1)),
    path('labtest/<int:pk>', views.labtestformset, name='labtest'),
    url(r'^labtest_ajax/', views.availablelabtestajaxsave, name='labtest_ajax'),
    url(r'^labmodel_form/', views.labajaxmodelsave, name='labajaxmodelsave'),
    url(
        r'^labtestauto/$',
        views.LabTestAutocomplete.as_view(),
        name="labtestauto",
    ),
]

# format_suffix_patterns(urlpatterns)