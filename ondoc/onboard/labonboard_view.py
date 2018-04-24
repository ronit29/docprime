from django.shortcuts import render, redirect, HttpResponse
from django.views import View
from .forms import LabForm, LabAddressForm, LabAwardFormSet, LabAccreditationFormSet, LabManagerFormSet, \
                    LabTimingFormSet, LabCertificationFormSet, LabServiceFormSet, \
                    LabAwardFormSetHelper, LabCertificationFormSetHelper, LabAccreditationFormSetHelper, \
                    LabManagerFormSetHelper, LabTimingFormSetHelper, FormSetHelper


# import models here
from ondoc.diagnostic.models import LabOnboardingToken, Lab, LabAward


class LabOnboard(View):

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
        formset_helper = FormSetHelper()
        award_formset_helper = LabAwardFormSetHelper()
        certificate_formset_helper = LabCertificationFormSetHelper()
        accreditation_formset_helper = LabAccreditationFormSetHelper()
        labmanager_formset_helper = LabManagerFormSetHelper()
        labtiming_formset_helper = LabTimingFormSetHelper()

        award_formset = LabAwardFormSet(instance = existing.lab, prefix="labaward")

        certificates_formset = LabCertificationFormSet(instance = existing.lab, prefix="labcertification")
        
        accreditation_formset = LabAccreditationFormSet(instance = existing.lab, prefix="labaccreditation")
        lab_manager_formset = LabManagerFormSet(instance = existing.lab, prefix="labmanager")
        lab_timing_formset = LabTimingFormSet(instance = existing.lab, prefix="labtiming")
        lab_service_formset = LabServiceFormSet(instance = existing.lab, prefix="labservice")

        return render(request, 'lab.html', {'lab_form': lab_form,
            'formset_helper': formset_helper,
            'lab_address_form': lab_address_form,
            'award_formset': award_formset,
            'certificates_formset': certificates_formset,
            'accreditation_formset': accreditation_formset,
            'lab_manager_formset': lab_manager_formset,
            'lab_timing_formset': lab_timing_formset,
            'lab_service_formset': lab_service_formset,
            'award_formset_helper': award_formset_helper,
            'certificate_formset_helper': certificate_formset_helper,
            'accreditation_formset_helper': accreditation_formset_helper,
            'labmanager_formset_helper': labmanager_formset_helper,
            'labtiming_formset_helper': labtiming_formset_helper
        })

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
        award_formset = LabAwardFormSet(request.POST, prefix = "labaward", instance = instance)
        if award_formset.is_valid():
            award_formset.save()
        else:
            print(award_formset.errors)


        # save accreditation formset
        accreditation_formset = LabAccreditationFormSet(request.POST, prefix = "labaccreditation", instance = instance)
        if accreditation_formset.is_valid():
            accreditation_formset.save()
        else:
            print(accreditation_formset.errors)


        # save certificates formset
        certificates_formset = LabCertificationFormSet(request.POST, prefix = "labcertification", instance = instance)
        if certificates_formset.is_valid():
            certificates_formset.save()

        # save lab_manager formset
        lab_manager_formset = LabManagerFormSet(request.POST, prefix = "labmanager", instance = instance)
        if lab_manager_formset.is_valid():
            lab_manager_formset.save()


        # save lab_timing formset
        lab_timing_formset = LabTimingFormSet(request.POST, prefix = "labtiming", instance = instance)
        if lab_timing_formset.is_valid():
            lab_timing_formset.save()

        return render(request, 'lab.html', {'lab_form': lab_form,
            'lab_address_form': lab_address_form,
            'award_formset': award_formset,
            'certificates_formset': certificates_formset,
            'accreditation_formset': accreditation_formset,
            'lab_manager_formset': lab_manager_formset,
            'lab_timing_formset': lab_timing_formset})
