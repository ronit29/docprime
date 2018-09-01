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
            return render(request,'onboard/access_denied.html')


        existing = None

        try:
            existing = LabOnboardingToken.objects.filter(token=token).order_by('-created_at')[0]
        except:
            pass

        if not existing:
            return render(request,'onboard/access_denied.html')


        if not existing.lab:
            return render(request,'onboard/access_denied.html')

        if existing.status == LabOnboardingToken.CONSUMED:
            return render(request, 'onboard/success.html')

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

        # lab_documents = LabDocument.objects.filter(lab=existing.lab)
        # Gather all forms
        lab_form = LabForm(instance = existing.lab, prefix='lab')
        lab_address_form = LabAddressForm(instance = existing.lab,prefix='labaddress')
        lab_open_form = LabOpenForm(instance = existing.lab,prefix='labopen')
        # Gather all formsets
        award_formset = LabAwardFormSet(instance = existing.lab, prefix="labaward")

        certificates_formset = LabCertificationFormSet(instance = existing.lab, prefix="labcertification")

        accreditation_formset = LabAccreditationFormSet(instance = existing.lab, prefix="labaccreditation")
        lab_manager_formset = LabManagerFormSet(instance = existing.lab, prefix="labmanager")
        lab_timing_formset = LabTimingFormSet(instance = existing.lab, prefix="labtiming")
        lab_service_formset = LabServiceFormSet(instance = existing.lab, prefix="labservice")
        lab_doctor_availability_formset = LabDoctorAvailabilityFormSet(instance = existing.lab, prefix="labdoctoravailability")
        lab_doctor_formset = LabDoctorFormSet(instance = existing.lab, prefix="labdoctor")

        message = request.session.get('message','')
        request.session['message'] = ''

        return render(request, 'onboard/lab.html', {'lab_form': lab_form,
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
            'message' : message,
            'lab' : existing.lab,
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
        lab_doctor_availability_formset = LabDoctorAvailabilityFormSet(request.POST, prefix = "labdoctoravailability", instance = instance)
        lab_doctor_formset = LabDoctorFormSet(request.POST, prefix = "labdoctor", instance = instance)
        certificates_formset = LabCertificationFormSet(request.POST, prefix = "labcertification", instance = instance)
        award_formset = LabAwardFormSet(request.POST, prefix = "labaward", instance = instance)
        accreditation_formset = LabAccreditationFormSet(request.POST, prefix = "labaccreditation", instance = instance)
        lab_manager_formset = LabManagerFormSet(request.POST, prefix = "labmanager", instance = instance)
        lab_timing_formset = LabTimingFormSet(request.POST, prefix = "labtiming", instance = instance)


        validate_req = [lab_manager_formset]
        min_num = 0
        validate_min = False

        if request.POST.get('_action',None) == '_submit':
            min_num = 1
            validate_min = True
            if 'labopen-always_open' not in request.POST:
                validate_req.append(lab_timing_formset)

        for x in validate_req:
            x.min_num = min_num
            x.validate_min = validate_min

        #service_missing = False
        #if 'lab_service_1' not in request.POST and 'lab_service_2' not in request.POST
        #    service_missing = True



        if not all([lab_form.is_valid(), lab_address_form.is_valid(), lab_open_form.is_valid(),lab_doctor_availability_formset.is_valid(),
            lab_doctor_formset.is_valid(), certificates_formset.is_valid(), award_formset.is_valid(),
            accreditation_formset.is_valid(), lab_manager_formset.is_valid(), lab_timing_formset.is_valid()
             ]):

            lab_images = LabImage.objects.filter(lab=instance)
            lab_doc_dict = OrderedDict()
            for id, value in LabDocument.CHOICES:
                results = LabDocument.objects.filter(lab=instance, document_type=id)
                if len(results)>0:
                    lab_doc_dict[id] = (id, value, results)
                else:
                    lab_doc_dict[id] = (id, value, None)

            address_components = ['building','sublocality','locality','city','state','country']
            address_values = []
            for x in address_components:
                if getattr(instance, x):
                    address_values.append(getattr(instance, x))

            address = ", ".join(address_values)

            lab_service_dict = {}
            for service in LabService.objects.filter(lab=instance):
                lab_service_dict[service.service] = service

            return render(request, 'onboard/lab.html', {'lab_form': lab_form,
                'lab_address_form': lab_address_form,
                'award_formset': award_formset,
                'certificates_formset': certificates_formset,
                'accreditation_formset': accreditation_formset,
                'lab_manager_formset': lab_manager_formset,
                'lab_timing_formset': lab_timing_formset,
                'lab_open_form' : lab_open_form,
                'lab_doctor_formset' : lab_doctor_formset,
                'lab_images' : lab_images,
                'lab_doc_dict' : lab_doc_dict,
                'address' : address,
                'lab_service_dict' : lab_service_dict,
                'LabService' : LabService,
                'lab_doctor_availability_formset' : lab_doctor_availability_formset,
                'error_message' : 'Please fill all required fields',
                'lab':instance,})



        lab_form.cleaned_data.update(lab_address_form.cleaned_data)
        lab_form.cleaned_data.update(lab_open_form.cleaned_data)
        lab_obj = lab_form.save()

        lab_doctor_availability_formset.save()
        lab_doctor_formset.save()
        certificates_formset.save()
        award_formset.save()
        accreditation_formset.save()
        lab_manager_formset.save()
        lab_timing_formset.save()


        for id, name in LabService.SERVICE_CHOICES:
            val = request.POST.get('labservice_'+str(id))
            if val:
                if not LabService.objects.filter(service=id, lab=instance).exists():
                    ls = LabService()
                    ls.lab = instance
                    ls.service = id
                    ls.save()
            else:
                LabService.objects.filter(service=id, lab=instance).delete()

        request.session['message'] = 'Successfully Saved Draft'

        action = request.POST.get('_action',None)

        if action=='_submit':
            instance.onboarding_status = Lab.ONBOARDED
            instance.save()
            LabOnboardingToken.objects.filter(token = token).update(status=LabOnboardingToken.CONSUMED)


        return redirect("/onboard/lab?token="+token, permanent=False)


        # return render(request, 'lab.html', {'lab_form': lab_form,
        #     'lab_address_form': lab_address_form,
        #     'award_formset': award_formset,
        #     'certificates_formset': certificates_formset,
        #     'accreditation_formset': accreditation_formset,
        #     'lab_manager_formset': lab_manager_formset,
        #     'lab_timing_formset': lab_timing_formset,
        #      'lab_open_form' : lab_open_form})
