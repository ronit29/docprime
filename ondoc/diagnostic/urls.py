from django.conf.urls import url, include
from django.urls import path
from . import views
from .api.v1.router import urlpatterns as v1

app_name = 'diagnostic'

urlpatterns = [
    # path('v1/', include(v1)),
    #path('labtest/<int:pk>', views.labtestformset, name='labtest'),
    url(r'^admin/ajax/labtest/save/', views.availablelabtestajaxsave, name='labtest_ajax'),
    url(r'^admin/ajax/csv/upload/', views.testcsvupload, name='csv_upload'),
    url(r'^admin/labpricing/save', views.labajaxmodelsave, name='labajaxmodelsave'),
    url(r'^admin/labmapview', views.lab_map_view, name='lab-map-view'),
    url(
        r'^admin/labtestauto/$',
        views.LabTestAutocomplete.as_view(),
        name="labtestauto",
    ),
]

# format_suffix_patterns(urlpatterns)