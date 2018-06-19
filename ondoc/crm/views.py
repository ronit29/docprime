from django.shortcuts import render
from django.contrib import auth
from ondoc.authentication.models import User
from django.shortcuts import HttpResponseRedirect


def login(request):
    mobile = request.GET.get('mobile')

    user = User.objects.filter(phone_number=mobile).first()
    auth.login(request, user)
    return HttpResponseRedirect("/api-docs")

    ##return render(request,'index.html')
