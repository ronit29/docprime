from rest_framework import status
from django.shortcuts import render
from django.contrib import messages
from .forms import OnlineLeadsForm, CareersForm, SearchDataForm
from django.http import HttpResponseRedirect, HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.conf import settings
from ondoc.crm.constants import constants
from ondoc.web import models as web_models
from django.contrib.auth import get_user_model
from ipware import get_client_ip
from django import forms
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

def index(request):
    if request.method == "POST":
        form = OnlineLeadsForm(request.POST)
        if form.is_valid():
            model_instance = form.save(commit=False)
            model_instance.save()
            messages.success(request, 'Submission Successful')
            return HttpResponseRedirect('/')
    else:
        form = OnlineLeadsForm()
    return render(request, 'index.html', {'form': form})


def terms_page(request):
    return render(request, 'terms-of-use.html')


def privacy_page(request):
    return render(request, 'privacy.html')


def media_page(request):
    return render(request, 'media.html')


def about_page(request):
    return render(request, 'aboutUs.html')


def contact_page(request):
    return render(request, 'contactUs.html')


def disclaimer_page(request):
    return render(request, 'disclaimer.html')


def howitworks_page(request):
    return render(request, 'howItWorks.html')


def user_appointment_via_agent(request):
    if not (request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists()
            or request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists()):
        return HttpResponseRedirect('%s' % settings.ADMIN_BASE_URL)
    api_domain = '%s%s' % ('', '/api/v1/admin/agent/user/login')
    appDomain = '%s%s' % (settings.CONSUMER_APP_DOMAIN, '/agent/login')
    return render(request, 'agentLogin.html', {'apiDomain': api_domain, 'appDomain': appDomain, 'user_type':User.CONSUMER})



def doctor_login_via_agent(request):
    if not (request.user.is_superuser):
        return HttpResponseRedirect('%s' % settings.ADMIN_BASE_URL)
    api_domain = '%s%s' % ('', '/api/v1/admin/agent/user/login')
    appDomain = '%s%s' % (settings.PROVIDER_APP_DOMAIN, '/agent/login')
    return render(request, 'agentLogin.html', {'apiDomain': api_domain, 'appDomain': appDomain, 'user_type':User.DOCTOR})


def careers_page(request):
    if request.method == "POST":
        form = CareersForm(request.POST, request.FILES)
        if form.is_valid():
            model_instance = form.save(commit=False)
            model_instance.save()
            messages.success(request, 'Form submission successful')
            return HttpResponseRedirect('/careers')
    else:
        form = CareersForm()
    return render(request, 'careers.html', {'form': form})


def redirect_to_original_url(request, hash):
    tiny_url = web_models.TinyUrl.objects.filter(short_code=hash).first()
    if not tiny_url:
        return HttpResponse(status=status.HTTP_404_NOT_FOUND)
    original_url = tiny_url.original_url
    try:
        ip_address, is_routable = get_client_ip(request)
        tiny_url_hit = web_models.TinyUrlHits.objects.create(tiny_url=tiny_url, ip_address=ip_address)
    except:
        logger.error("Error in inserting into TinyUrlHit table")
    return HttpResponseRedirect(original_url)


def upload_search_data(request):
    from ondoc.api.v1.common.views import UpdateXlsViewSet
    form = SearchDataForm()
    error = False
    if request.method == "POST" and request.FILES.get('file'):
        call_csv_up = UpdateXlsViewSet()
        file = call_csv_up.update(request)
        if file:
            request.FILES.pop('file')
            return file
        else:
            error = True

    return render(request, 'search-data.html', {'form': form, 'error': error})