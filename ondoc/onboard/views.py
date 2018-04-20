from random import randint
from django.views import View
from django.shortcuts import render, redirect, HttpResponse

# import models here
from ondoc.diagnostic.models import LabOnboardingToken, Lab, LabAward

# import forms here.
from .forms import LabForm, OTPForm, LabCertificationForm, LabAwardForm, LabAddressForm

# import formsets here.
from .forms import LabAwardFormSet, LabCertificationFormSet, LabAccreditationFormSet, LabManagerFormSet, \
                    LabTimingFormSet


class BaseOnboard(View):

    def get(self, request):
        id = request.GET.get('id')
        token = request.GET.get('token')

        if not id or not token:
            return HttpResponse('error')

        try:
            existing = LabOnboardingToken.objects.filter(lab_id=id,token=token, status = LabOnboardingToken.GENERATED).order_by('-created_at')[0]
        except:
            return HttpResponse('error')

        if not existing.lab:
            return HttpResponse('error')

        # Gather all forms
        lab_form = LabForm(instance = existing.lab)
        lab_address_form = LabAddressForm(instance = existing.lab)

        # Gather all formsets
        award_formset = LabAwardFormSet(instance = existing.lab, prefix="nested")
        certificates_formset = LabCertificationFormSet(instance = existing.lab, prefix="nested")
        accreditation_formset = LabAccreditationFormSet(instance = existing.lab, prefix="nested")
        lab_manager_formset = LabManagerFormSet(instance = existing.lab, prefix="nested")
        lab_timing_formset = LabTimingFormSet(instance = existing.lab, prefix="nested")

        return render(request, 'lab.html', {'lab_form': lab_form,
            'lab_address_form': lab_address_form,
            'award_formset': award_formset,
            'certificates_formset': certificates_formset,
            'accreditation_formset': accreditation_formset,
            'lab_manager_formset': lab_manager_formset,
            'lab_timing_formset': lab_timing_formset
        })

    def post(self, request):
        pass


def otp(request):
    if request.method == 'POST':
        action = request.POST.get('_resend_otp')
        if action:
            otp = randint(1000000000, 9000000000)
            print(otp)
            request.session['otp'] = otp
            lab_id = request.GET.get('lab_id')
            # token = request.GET.get('lab_id')
            return redirect("/onboard/lab?lab_id="+lab_id, permanent=False)
        else:
            stored_otp = str(request.session.get('otp',''))
            otp = request.POST.get('otp')
            if otp == stored_otp:
                return redirect("/onboard/lab?token=1438749146&lab_id=1", permanent=False)
    else:
        form = OTPForm()
        return render(request,'otp.html',{'form':form})


def generate(request):
    lab_id = request.GET.get('lab_id')
    lab = Lab.objects.get(pk=lab_id)

    LabOnboardingToken.objects.filter(lab_id=lab_id, status=LabOnboardingToken.GENERATED).update(status=LabOnboardingToken.REJECTED)
    
    token = LabOnboardingToken(status=1,lab_id=lab_id, token=randint(1000000000, 9000000000),verified_token=randint(1000000000, 9000000000) )
    token.save()
    url = 'ondoc.com/onboard/lab?token='+str(token.token)+'&lab_id='+str(lab_id)
    return HttpResponse('generated_url is '+url)
