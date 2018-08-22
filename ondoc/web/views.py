from django.shortcuts import render
from django.contrib import messages
from .forms import OnlineLeadsForm, CareersForm
from django.http import HttpResponseRedirect
from django.conf import settings


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

def agenntlogin_page(request):
    api_domain = '%s%s' % (settings.BASE_URL, '/api/v1/user/agent/login/')
    appDomain = 'https://%s%s' % (settings.CONSUMER_APP_DOMAIN, '/agent/login')
    return render(request, 'agentLogin.html', {'apiDomain': api_domain, 'appDomain': appDomain})


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


