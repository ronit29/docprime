from dal import autocomplete
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
import urllib
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

User = get_user_model()

def index(request):
    # if request.method == "POST":
    #     form = OnlineLeadsForm(request.POST)
    #     if form.is_valid():
    #         model_instance = form.save(commit=False)
    #         model_instance.save()
    #         messages.success(request, 'Submission Successful')
    #         return HttpResponseRedirect('/')
    # else:
    #     form = OnlineLeadsForm()
    #return render(request, 'index.html', {'form': form})
    return render(request, 'blank.html')

#@require_http_methods(["GET"])
def redirect_to_app(request):
    anroid_url = 'https://play.google.com/store/apps/details?id=com.docprime'
    ios_url = 'https://itunes.apple.com/us/app/docprime-consult-online/id1449704799?ls=1&mt=8'
    web_url = 'https://docprime.com'
    os = request.user_agent.os.family
    url = web_url
    if os=='iOS':
        url = ios_url
    elif os=='Android':
        url = anroid_url

    separator = '?'
    if '?' in url:
        separator = '&'
        
    data = dict()
    for k in request.GET.keys():
        data[k] = request.GET.get(k)
    params = urllib.parse.urlencode(data)
    if params:
        url = url+separator+params
    
    return redirect(url, permanent=False)

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
    # api_domain = '%s%s' % (settings.CONSUMER_APP_DOMAIN, '/api/v1/admin/agent/user/login')
    appDomain = '%s%s' % (settings.CONSUMER_APP_DOMAIN, '/agent/login')
    return render(request, 'agentLogin.html', {'apiDomain': api_domain, 'appDomain': appDomain, 'user_type':User.CONSUMER})



def doctor_login_via_agent(request):
    if not (request.user.is_superuser or request.user.groups.filter(name='provider_group').exists()):
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


def advanced_doctor_search_view(request):
    from ondoc.doctor.models import Hospital, PracticeSpecialization
    from django_select2.forms import Select2MultipleWidget

    class SearchDataForm(forms.Form):
        # hospital = forms.ModelMultipleChoiceField(queryset=Hospital.objects.filter(is_live=True), widget=Select2MultipleWidget)
        hospital = forms.ModelMultipleChoiceField(queryset=Hospital.objects.filter(is_live=True), widget=autocomplete.ModelSelect2Multiple(url='hospital-autocomplete'))
        # specialization = forms.ModelMultipleChoiceField(queryset=PracticeSpecialization.objects.all(),
        #                                                 widget=Select2MultipleWidget)
        specialization = forms.ModelMultipleChoiceField(queryset=PracticeSpecialization.objects.all(),
                                                        widget=autocomplete.ModelSelect2Multiple(url='practicespecialization-autocomplete'))

    from django.contrib import messages
    if request.method == "POST":
        form = SearchDataForm(request.POST, request.FILES)
        if form.is_valid():
            messages.add_message(request, messages.SUCCESS, "Link Created")
            required_link = '{}/opd/searchresults?specializations={}&conditions=&lat=&long=&sort_on=&sort_order=&availability=&gender=&avg_ratings=&doctor_name=&hospital_name=&locationType=autoComplete&procedure_ids=&procedure_category_ids=&hospital_id={}&ipd_procedures=&is_insured=false&locality=&sub_locality=&sits_at_hospital=false&sits_at_clinic=false'.format(
                settings.CONSUMER_APP_DOMAIN,
                ",".join([str(x) for x in form.cleaned_data['specialization'].all().values_list('id', flat=True)]),
                ",".join([str(x) for x in form.cleaned_data['hospital'].all().values_list('id', flat=True)]))
            return render(request, 'doctorSearch.html', {'form': form, 'required_link': required_link})
    else:
        form = SearchDataForm()
    return render(request, 'doctorSearch.html', {'form': form})
