from django.shortcuts import render, redirect, HttpResponse
from django.views import View
from collections import OrderedDict

from .forms import LabForm, LabAddressForm, LabOpenForm, LabAwardFormSet, LabAccreditationFormSet, LabManagerFormSet, \
                    LabTimingFormSet, LabCertificationFormSet, LabServiceFormSet, LabDoctorAvailabilityFormSet, \
                    LabDoctorFormSet
                    # LabAwardFormSetHelper, LabCertificationFormSetHelper, LabAccreditationFormSetHelper, \
                    # LabManagerFormSetHelper, LabTimingFormSetHelper, FormSetHelper


# import models here
from ondoc.diagnostic.models import LabOnboardingToken, Lab, LabAward, LabService, LabDoctorAvailability, LabImage, LabDocument


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
            return render(request, 'access_denied.html')

        auth = request.session.get(token, False)

        if not auth:
            return redirect("/onboard/otp?token="+token, permanent=False)

        address_components = ['building','sublocality','locality','city','state','country']
        address_values = []
        for x in address_components:
            if getattr(existing.lab, x):
                address_values.append(getattr(existing.lab, x))

        address = ", ".join(address_values)


        lab_service_dict = {}
        for service in LabService.objects.filter(lab=existing.lab):
            lab_service_dict[service.service] = service


        # We need to pregenerate the doctor availability entries to show on the form
        for slot, name in LabDoctorAvailability.SLOT_CHOICES:
            if not LabDoctorAvailability.objects.filter(slot=slot, lab=existing.lab).exists():
                lb = LabDoctorAvailability()
                lb.slot = slot
                lb.lab = existing.lab
                lb.save()

        lab_images = LabImage.objects.filter(lab=existing.lab)

        lab_doc_dict = OrderedDict()
        for id, value in LabDocument.CHOICES:
            results = LabDocument.objects.filter(lab=existing.lab, document_type=id)
            if len(results)>0:
                lab_doc_dict[id] = (id, value, results)
            else:
                lab_doc_dict[id] = (id, value, None)

        lab_documents = LabDocument.objects.filter(lab=existing.lab)
        # Gather all forms
        lab_form = LabForm(instance = existing.lab, prefix='lab')
        lab_address_form = LabAddressForm(instance = existing.lab,prefix='labaddress')
        lab_open_form = LabOpenForm(instance = existing.lab,prefix='labopen')
        # Gather all formsets
        award_formset = LabAwardFormSet(instance = existing.lab, prefix="labaward")

        certificates_formset = LabCertificationFormSet(instance = existing.lab, prefix="labcertificates")

        accreditation_formset = LabAccreditationFormSet(instance = existing.lab, prefix="labaccreditation")
        lab_manager_formset = LabManagerFormSet(instance = existing.lab, prefix="labmanager")
        lab_timing_formset = LabTimingFormSet(instance = existing.lab, prefix="labtiming")
        lab_service_formset = LabServiceFormSet(instance = existing.lab, prefix="labservice")
        lab_doctor_availability_formset = LabDoctorAvailabilityFormSet(instance = existing.lab, prefix="labdoctoravailability")
        lab_doctor_formset = LabDoctorFormSet(instance = existing.lab, prefix="labdoctor")


        return render(request, 'lab.html', {'lab_form': lab_form,
            'lab_address_form': lab_address_form,
            'lab_open_form' : lab_open_form,
            'award_formset': award_formset,
            'certificates_formset': certificates_formset,
            'accreditation_formset': accreditation_formset,
            'lab_manager_formset': lab_manager_formset,
            'lab_timing_formset': lab_timing_formset,
            'lab_service_formset': lab_service_formset,
            'labAddressForm': LabAddressForm(),
            'LabDoctorAvailability':LabDoctorAvailability,
            'LabService':LabService,
            'lab_service_dict': lab_service_dict,
            'lab_doctor_availability_formset' : lab_doctor_availability_formset,
            'lab_doctor_formset' : lab_doctor_formset,
            'address' : address,
            'lab_images' : lab_images,
            'lab_doc_dict' : lab_doc_dict,
            'LabDocument' : LabDocument,
            })

    def post(self, request):
        token = request.GET.get('token')
        try:
            instance = LabOnboardingToken.objects.filter(token = token)[0].lab
        except:
            return HttpResponse('invalid token')

        lab_form = LabForm(request.POST, instance = instance, prefix = "lab")
        lab_address_form = LabAddressForm(request.POST, instance = instance, prefix = "labaddress")
        lab_open_form = LabOpenForm(request.POST, instance = instance, prefix = "labopen")

        if all([lab_form.is_valid(), lab_address_form.is_valid(), lab_open_form.is_valid()]):
            lab_form.cleaned_data.update(lab_address_form.cleaned_data)
            lab_form.cleaned_data.update(lab_open_form.cleaned_data)
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
