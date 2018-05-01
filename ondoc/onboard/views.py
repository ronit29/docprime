from django.shortcuts import render, redirect, HttpResponse
from django.http import JsonResponse
from random import randint
from ondoc.sms import api
from ondoc.sendemail import api as email_api
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
        #return HttpResponse('Invalid URL. Token is required')
        return render(request,'access_denied.html')


    existing = None

    try:
        existing = LabOnboardingToken.objects.filter(token=token).order_by('-created_at')[0]
    except:
        pass

    if not existing:
        return render(request,'access_denied.html')

    if not existing.lab:
        return render(request,'access_denied.html')


    if existing.status != LabOnboardingToken.GENERATED:
        return render(request,'access_denied.html')

    auth = request.session.get(token, False)
    if auth:
        return redirect("/onboard/lab?token="+token, permanent=False)


    if request.method == 'POST':
        action = request.POST.get('_resend_otp')
        if action:
            otp = randint(200000, 900000)
            message = 'You have initiated onboarding process for '+existing.lab.name+'. OTP is '+str(otp)
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
        existingOTP = request.session.get('otp',None)

        label = 'Verify your Registered Mobile Number '+str(existing.lab.primary_mobile)
        page = 'otp_request'

        if existingOTP:
            page = 'otp_verify'
            label = '6 Digit verification code has been send to your mobile number '+str(existing.lab.primary_mobile)

        
            # form.fields['otp'].widget = HiddenInput()

            # otp = randint(200000, 900000)
            # message = 'You have initiated onboarding process for '+existing.lab.name+'. OTP is '+str(otp)
            #api.send_sms(message, '91'+str(existing.lab.primary_mobile))
            #request.session['otp'] = otp



    return render(request,'otp.html',{'label':label, 'page':page, 'otp_resent':otp_resent, 'otp_mismatch':otp_mismatch})


def generate(request):
    if not request.is_ajax():
        return HttpResponse('invalid request')

    host = request.get_host()
    lab_id = request.POST.get('lab_id')
    lab = Lab.objects.get(pk=lab_id)

    LabOnboardingToken.objects.filter(lab_id=lab_id, status=LabOnboardingToken.GENERATED).update(status=LabOnboardingToken.REJECTED)

    token = LabOnboardingToken(status=1,email=lab.primary_email,mobile=lab.primary_mobile,lab_id=lab_id, token=randint(1000000000, 9000000000))
    token.save()
    url = host + '/onboard/lab?token='+str(token.token)

    message =  ('Dear Sir/Mam,'
                'Please find below the enrolment URL Link:-'
                'We request you to kindly complete the form by filling an empanelment form to start working together for patient requirements like consultations and investigations.'
                'Our agreed rate list along with terms and condition are available on the link for your kind perusal.'
                'For any queries you can connect with our representative over the phone which is already associated with you.'
                )


    email_api.send_email(lab.primary_email, 'Onboarding link for '+lab.name, message)
    lab.onboarding_status = lab.REQUEST_SENT
    lab.save()

    # qprint("The generated onboarding url is: " + url)
    return JsonResponse({'message': 'ok'})

def generate_doctor(request):
    if not request.is_ajax():
        return HttpResponse('invalid request')

    host = request.get_host()
    doctor_id = request.POST.get('doctor_id')
    doctor = Doctor.objects.get(pk=doctor_id)

    DoctorOnboardingToken.objects.filter(doctor_id=doctor_id, status=DoctorOnboardingToken.GENERATED).update(status=DoctorOnboardingToken.REJECTED)

    token = DoctorOnboardingToken(status=1,email=doctor.email,mobile=doctor.primary_mobile,doctor_id=doctor_id, token=randint(1000000000, 9000000000))
    token.save()
    url = host + '/onboard/doctor?token='+str(token.token)
    email_api.send_email(doctor.email, 'Onboarding link for '+doctor.name, 'Your onboarding url is '+url)
    doctor.onboarding_status = doctor.REQUEST_SENT
    doctor.save()

    # qprint("The generated onboarding url is: " + url)
    return JsonResponse({'message': 'ok'})


def terms(request):
    return render(request,'terms.html')
