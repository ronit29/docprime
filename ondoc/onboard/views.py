from django.shortcuts import render, redirect, HttpResponse
from random import randint
from django.views import View
from django.shortcuts import render, redirect, HttpResponse
from ondoc.sms import api

# import models here
from ondoc.diagnostic.models import LabOnboardingToken, Lab, LabAward

# import forms here.
from .forms import LabForm, OTPForm, LabCertificationForm, LabAwardForm, LabAddressForm

# import formsets here.
from .forms import LabAwardFormSet, LabCertificationFormSet, LabAccreditationFormSet, LabManagerFormSet, \
                    LabTimingFormSet



class BaseOnboard(View):

    def get(self, request):

        token = request.GET.get('token')

        if not token:
            return HttpResponse('Invalid URL')

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

        auth = request.session.get(token, False)


        if not auth:
            return redirect("/onboard/otp?token="+token, permanent=False)


        # Gather all forms
        lab_form = LabForm(instance = existing.lab, prefix = "lab")
        lab_address_form = LabAddressForm(instance = existing.lab, prefix = "labaddress")

        # Gather all formsets
        award_formset = LabAwardFormSet(instance = existing.lab, prefix="labaward")
        certificates_formset = LabCertificationFormSet(instance = existing.lab, prefix="labcertification")
        accreditation_formset = LabAccreditationFormSet(instance = existing.lab, prefix="labaccreditation")
        lab_manager_formset = LabManagerFormSet(instance = existing.lab, prefix="labmanager")
        lab_timing_formset = LabTimingFormSet(instance = existing.lab, prefix="labtiming")

        return render(request, 'lab.html', {'lab_form': lab_form,
            'lab_address_form': lab_address_form,
            'award_formset': award_formset,
            'certificates_formset': certificates_formset,
            'accreditation_formset': accreditation_formset,
            'lab_manager_formset': lab_manager_formset,
            'lab_timing_formset': lab_timing_formset})

    def post(self, request):
        token = request.GET.get('token')
        try:
            instance = LabOnboardingToken.objects.filter(token = token)[0].lab
        except:
            return HttpResponse('invalid token')

        lab_form = LabForm(request.POST, instance = instance, prefix = "lab")
        lab_address_form = LabAddressForm(request.POST, instance = instance, prefix = "labaddress")


        if all([lab_form.is_valid(), lab_address_form.is_valid()]):
            lab_form.cleaned_data.update(lab_address_form.cleaned_data)
            lab_obj = lab_form.save()
        else:
            return HttpResponse('invalid forms')

        # Now we save the related forms
        # save awards formset
        award_formset = LabAwardFormSet(data=request.POST, prefix = "labaward", instance = lab_obj)
        if award_formset.is_valid():
            award_formset.save()

        # save certificates formset
        certificates_formset = LabCertificationFormSet(request.POST, prefix = "labcertification", instance = lab_obj)
        if certificates_formset.is_valid():
            certificates_formset.save()

        # save accreditation formset
        accreditation_formset = LabAccreditationFormSet(request.POST, prefix = "labaccreditation", instance = lab_obj)
        if accreditation_formset.is_valid():
            accreditation_formset.save()

        # save lab_manager formset
        lab_manager_formset = LabManagerFormSet(request.POST, prefix = "labmanager", instance = lab_obj)
        if lab_manager_formset.is_valid():
            lab_manager_formset.save()


        # save lab_timing formset
        lab_timing_formset = LabTimingFormSet(request.POST, prefix = "labtiming", instance = lab_obj)
        if lab_timing_formset.is_valid():
            lab_timing_formset.save()

        return render(request, 'lab.html', {'lab_form': lab_form,
            'lab_address_form': lab_address_form,
            'award_formset': award_formset,
            'certificates_formset': certificates_formset,
            'accreditation_formset': accreditation_formset,
            'lab_manager_formset': lab_manager_formset,
            'lab_timing_formset': lab_timing_formset})





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
                return redirect("/onboard/lab?token=1438749146", permanent=False)
            else:
                request.session['otp_mismatch'] = True
                return redirect("/onboard/otp?token=1438749146", permanent=False)
    else:
        otp_resent = request.session.get('otp_resent', False)
        otp_mismatch = request.session.get('otp_mismatch', False)
        request.session['otp_resent'] = False
        request.session['otp_mismatch'] = False

        form = OTPForm()
        return render(request,'otp.html',{'form':form, 'otp_resent':otp_resent, 'otp_mismatch':otp_mismatch})


def generate(request):
    lab_id = request.GET.get('lab_id')
    lab = Lab.objects.get(pk=lab_id)

    LabOnboardingToken.objects.filter(lab_id=lab_id, status=LabOnboardingToken.GENERATED).update(status=LabOnboardingToken.REJECTED)

    token = LabOnboardingToken(status=1,lab_id=lab_id, token=randint(1000000000, 9000000000),verified_token=randint(1000000000, 9000000000))
    token.save()
    url = 'ondoc.com/onboard/lab?token='+str(token.token)+'&lab_id='+str(lab_id)
    return HttpResponse('generated_url is '+url)
