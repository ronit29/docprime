"""test URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import include, path
from django.conf.urls import url

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.conf import settings

# DEBUG = env.bool('DJANGO_DEBUG', default=True)

additional_urls = [
    # path('doctors/', include('ondoc.doctor.urls')),
    # path('auth/', include('ondoc.authentication.urls')),
    # path('diagnostic/', include('ondoc.diagnostic.urls')),
    path('api/', include('ondoc.api.urls')),
    path('', include('ondoc.articles.urls'))
    ]

if not settings.API_ENABLED:
    additional_urls = []
    
# else:
#     from rest_framework_swagger.views import get_swagger_view
#     schema_view = get_swagger_view(title='DocPrime API')

#     additional_urls += [path('api-docs', schema_view)]


urlpatterns = [
    path('admin/', admin.site.urls),
    path('nested_admin/', include('nested_admin.urls')),
    path('', include('ondoc.diagnostic.urls', namespace='diagnostic')),
    path('', include('ondoc.web.urls', namespace='web')),
    path('', include('ondoc.matrix.urls', namespace='matrix')),
    path('', include('ondoc.doctor.urls', namespace='doctor')),
    path('onboard/', include('ondoc.onboard.urls', namespace='onboard')),
    path('', include('ondoc.seo.urls')),
    url(r'^select2/', include('django_select2.urls')),
] + additional_urls + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# urlpatterns += [url(r'^silk/', include('silk.urls', namespace='silk'))]
#urlpatterns += [url(r'^silk/', include('silk.urls', namespace='silk'))]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('admin/__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns