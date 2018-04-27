from django.shortcuts import render, redirect, HttpResponse
from django.http import JsonResponse
from random import randint
from ondoc.sms import api

# import models here
from ondoc.diagnostic.models import LabOnboardingToken, Lab, LabAward
from ondoc.doctor.models import DoctorOnboardingToken, Doctor


# import forms here.
from .forms import LabForm, OTPForm, LabCertificationForm, LabAwardForm, LabAddressForm

#import other views
from .doctoronboard_view import DoctorOnboard
from .labonboard_view import LabOnboard

def otp(request):

    token = request.GET.get('token')

    if not token:
        return HttpResponse('Invalid URL. Token is required')

    existing = None

    try:
        existing = LabOnboardingToken.objects.filter(token=token).order_by('-created_at')[0]
    except:
        pass

    if not existing:
        return HttpResponse('Invalid Token')

    if not existing.lab:
        return HttpResponse('No lab found for this token')


    if existing.status != LabOnboardingToken.GENERATED:
        return render(request,'access_denied.html')

    if request.method == 'POST':
        action = request.POST.get('_resend_otp')
        if action:
            otp = randint(200000, 900000)
            message = 'OTP is '+str(otp)
            api.send_sms(message, '91'+str(existing.lab.primary_mobile))

            # print(otp)
            request.session['otp'] = otp
            request.session['otp_resent'] = True
            # request.session['otp_verified'] = True
            return redirect("/onboard/otp?token="+token, permanent=False)
        else:
            stored_otp = str(request.session.get('otp',''))
            otp = request.POST.get('otp')
            if otp == stored_otp:
                request.session[token] = True
                request.session["token_value"] = token
                return redirect("/onboard/lab?token=" + token, permanent=False)
            else:
                request.session['otp_mismatch'] = True
                return redirect("/onboard/otp?token="+token, permanent=False)
    else:
        otp_resent = request.session.get('otp_resent', False)
        otp_mismatch = request.session.get('otp_mismatch', False)
        request.session['otp_resent'] = False
        request.session['otp_mismatch'] = False

        form = OTPForm()
        return render(request,'otp.html',{'form':form, 'otp_resent':otp_resent, 'otp_mismatch':otp_mismatch})


def generate(request):
    if not request.is_ajax():
        return HttpResponse('invalid request') 

    host = request.get_host()
    lab_id = request.POST.get('lab_id')
    lab = Lab.objects.get(pk=lab_id)

    LabOnboardingToken.objects.filter(lab_id=lab_id, status=LabOnboardingToken.GENERATED).update(status=LabOnboardingToken.REJECTED)

    token = LabOnboardingToken(status=1,lab_id=lab_id, token=randint(1000000000, 9000000000),verified_token=randint(1000000000, 9000000000))
    token.save()
    url = host + '/onboard/lab?token='+str(token.token)+'&lab_id='+str(lab_id)
    return JsonResponse({'url': url})
