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
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from ondoc import crm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('doctors/', include('ondoc.doctor.urls')),
    path('',include('ondoc.crm.urls')),
    path('auth/', include('ondoc.authentication.urls'))

    # path('api/crm/', include('ondoc.crm.urls')),
    # path('api/auth/', include('ondoc.authentication.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('admin/__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
