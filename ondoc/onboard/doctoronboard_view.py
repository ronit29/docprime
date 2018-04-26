from django.shortcuts import render, redirect, HttpResponse
from django.views import View
from .forms import  DoctorHospitalFormSet, DoctorLanguageFormSet, DoctorAwardFormSet, \
                     DoctorAssociationFormSet, DoctorExperienceFormSet


# import models here
from ondoc.doctor.models import DoctorOnboardingToken, Doctor


class DoctorOnboard(View):

    def get(self, request):
        token = request.GET.get('token')

        if not token:
            return HttpResponse('Invalid URL')

        existing = None

        try:
            existing = DoctorOnboardingToken.objects.filter(token=token).order_by('-created_at')[0]
        except:
            pass

        if not existing:
            return HttpResponse('Invalid Token')

        if not existing.doctor:
            return HttpResponse('No doctor found for this token')

        if existing.status != DoctorOnboardingToken.GENERATED:
            return render(request,'access_denied.html')

        auth = request.session.get(token, False)

        if not auth:
            return redirect("/onboard/otp?token="+token, permanent=False)

        # Gather all forms
        doctor_form = DoctorForm(instance = existing.doctor, prefix = "doctor")

        # GAther the formsets
        mobile_formset = DoctorMobileFormSet(instance = existing.doctor, prefix = 'doctormobile')
        qualification_formset = DoctorQualificationFormSet(instance = existing.doctor, prefix = 'doctorqualification')
        hospital_formset = DoctorHospitalFormSet(instance = existing.doctor, prefix = 'doctorhospital')
        language_formset = DoctorLanguageFormSet(instance = existing.doctor, prefix = 'doctorlanguage')
        award_formset = DoctorAwardFormSet(instance = existing.doctor, prefix = 'doctoraward')
        association_formset = DoctorAssociationFormSet(instance = existing.doctor, prefix = 'doctorassociation')
        experience_formset = DoctorExperienceFormSet(instance = existing.doctor, prefix = 'doctorexperience')
        medicalservice_formset = DoctorServiceFormSet(instance = existing.doctor, prefix = 'doctormedicalservice')
        image_formset = DoctorImageFormSet(instance = existing.doctor, prefix = 'doctorimage')

        return render(request, 'doctor.html', {'doctor_form': doctor_form,
            'mobile_formset': mobile_formset,
            'qualification_formset': qualification_formset,
            'hospital_formset': hospital_formset,
            'language_formset': language_formset,
            'award_formset': award_formset,
            'association_formset': association_formset,
            'experience_formset': experience_formset,
            'medicalservice_formset': medicalservice_formset,
            'image_formset': image_formset,
        })

    def post(self, request):
        token = request.GET.get('token')
        try:
            instance = DoctorOnboardingToken.objects.filter(token = token)[0].doctor
        except:
            return HttpResponse('invalid token')

        doctor_form = DoctorForm(request.POST, instance = instance, prefix = "doctor")

        if doctor_form.is_valid():
            doctor_obj = doctor_form.save()
        else:
            return HttpResponse('invalid forms')

        # Now we save the related forms
        # save awards formset
        mobile_formset = DoctorMobileFormSet(data=request.POST, instance = doctor_obj, prefix = "doctormobile")
        if mobile_formset.is_valid():
            mobile_formset.save()

        qualification_formset = DoctorQualificationFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorqualification')
        if qualification_formset.is_valid():
            qualification_formset.save()

        hospital_formset = DoctorHospitalFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorhospital')
        if hospital_formset.is_valid():
            hospital_formset.save()

        language_formset = DoctorLanguageFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorlanguage')
        if language_formset.is_valid():
            language_formset.save()

        award_formset = DoctorAwardFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctoraward')
        if award_formset.is_valid():
            award_formset.save()

        association_formset = DoctorAssociationFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorassociation')
        if association_formset.is_valid():
            association_formset.save()

        experience_formset = DoctorExperienceFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorexperience')
        if experience_formset.is_valid():
            experience_formset.save()

        medicalservice_formset = DoctorServiceFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctormedicalservice')
        if medicalservice_formset.is_valid():
            medicalservice_formset.save()

        image_formset = DoctorImageFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorimage')
        if image_formset.is_valid():
            image_formset.save()


        return render(request, 'doctor.html', {'doctor_form': doctor_form,
            'mobile_formset': mobile_formset,
            'qualification_formset': qualification_formset,
            'hospital_formset': hospital_formset,
            'language_formset': language_formset,
            'award_formset': award_formset,
            'association_formset': association_formset,
            'experience_formset': experience_formset,
            'medicalservice_formset': medicalservice_formset,
            'image_formset': image_formset,
        })
