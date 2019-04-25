from django.shortcuts import render, redirect, HttpResponse
from django.views import View
from collections import OrderedDict

from .forms import  DoctorClinicFormSet, DoctorLanguageFormSet, DoctorAwardFormSet, \
                     DoctorAssociationFormSet, DoctorExperienceFormSet, DoctorForm, \
                     DoctorMobileFormSet, DoctorQualificationFormSet, DoctorServiceFormSet, \
                     DoctorEmailFormSet, DoctorClinicTimingFormSet, BaseDoctorEmailFormSet
from django.db.models import Q
import datetime
# import models here
from ondoc.doctor.models import DoctorOnboardingToken, Doctor, DoctorImage, DoctorDocument, DoctorClinic
from random import randint
from ondoc.sms import api
from ondoc.sendemail import api as email_api
import logging

logger = logging.getLogger(__name__)

class DoctorOnboard(View):

    def get(self, request):
        token = request.GET.get('token')

        if not token:
            return render(request, 'onboard/access_denied.html')

        existing = None

        try:
            existing = DoctorOnboardingToken.objects.filter(token=token).order_by('-created_at')[0]
        except:
            pass

        if not existing:
            return render(request,'onboard/access_denied.html')

        if not existing.doctor:
            return render(request,'onboard/access_denied.html')

        if existing.status == DoctorOnboardingToken.CONSUMED:
            return render(request, 'onboard/dsuccess.html')

        if existing.status != DoctorOnboardingToken.GENERATED:
            return render(request,'onboard/access_denied.html')

        auth = request.session.get(token, False)

        if not auth:
            return redirect("/onboard/doctor/otp?token="+token, permanent=False)
        doc_images = DoctorImage.objects.filter(doctor=existing.doctor)

        billing_required = DoctorClinic.objects.filter(
            Q(hospital__network__is_billing_enabled=False, hospital__is_billing_enabled=False, doctor=existing.doctor) |
            Q(hospital__network__isnull=True, hospital__is_billing_enabled=False, doctor=existing.doctor)).exists()

        doc_dict = OrderedDict()
        for id, value in DoctorDocument.CHOICES:
            results = DoctorDocument.objects.filter(doctor=existing.doctor, document_type=id)
            if len(results)>0:
                doc_dict[id] = (id, value, results)
            else:
                doc_dict[id] = (id, value, None)

        message = request.session.get('message','')
        request.session['message'] = ''


        # Gather all forms
        doctor_form = DoctorForm(instance = existing.doctor, prefix = "doctor")

        hospitaltiming_formset = {}
        for timing in existing.doctor.doctor_clinics.all():
            hospitaltiming_formset[timing.id] = DoctorClinicTimingFormSet(instance=timing, prefix='doctorclinictiming')

        # GAther the formsets
        #email_formset = DoctorEmailFormSet(instance = existing.doctor, formset = BaseDoctorEmailFormSet, prefix = 'doctoremail')
        email_formset = DoctorEmailFormSet(instance = existing.doctor, prefix = 'doctoremail')
        #mobile_formset = DoctorMobileFormSet(instance = existing.doctor, formset = BaseDoctorMobileFormSet, prefix = 'doctormobile')
        mobile_formset = DoctorMobileFormSet(instance = existing.doctor, prefix = 'doctormobile')
        qualification_formset = DoctorQualificationFormSet(instance=existing.doctor, prefix = 'doctorqualification')
        hospital_formset = DoctorClinicFormSet(instance=existing.doctor, prefix='doctorclinic')
        language_formset = DoctorLanguageFormSet(instance = existing.doctor, prefix = 'doctorlanguage')
        award_formset = DoctorAwardFormSet(instance = existing.doctor, prefix = 'doctoraward')
        association_formset = DoctorAssociationFormSet(instance = existing.doctor, prefix = 'doctorassociation')
        experience_formset = DoctorExperienceFormSet(instance = existing.doctor, prefix = 'doctorexperience')
        medicalservice_formset = DoctorServiceFormSet(instance = existing.doctor, prefix = 'doctormedicalservice')
        # image_formset = DoctorImageFormSet(instance = existing.doctor, prefix = 'doctorimage')


        return render(request, 'onboard/doctor.html', {'doctor_form': doctor_form,
            'email_formset': email_formset,
            'mobile_formset': mobile_formset,
            'qualification_formset': qualification_formset,
            'hospital_formset': hospital_formset,
            'hospitaltiming_formset': hospitaltiming_formset,
            'language_formset': language_formset,
            'award_formset': award_formset,
            'association_formset': association_formset,
            'experience_formset': experience_formset,
            'medicalservice_formset': medicalservice_formset,            
            'doc_images' : doc_images,
            'doc_dict' : doc_dict,
            'DoctorDocument' : DoctorDocument,
            'billing_required': billing_required,
            'message' : message})

    def post(self, request):
        token = request.GET.get('token')
        try:
            instance = DoctorOnboardingToken.objects.filter(token = token)[0].doctor
        except:
            return HttpResponse('invalid token')

        doctor_obj = instance

        hospitaltiming_formset = {}
        for timing in doctor_obj.doctor_clinics.all():
            hospitaltiming_formset[timing.id] = DoctorClinicTimingFormSet(instance=timing, prefix='doctorclinictiming')

        doctor_form = DoctorForm(request.POST, instance = instance, prefix = "doctor")

        mobile_formset = DoctorMobileFormSet(data=request.POST, instance = doctor_obj, prefix = "doctormobile")
        email_formset = DoctorEmailFormSet(data=request.POST, instance = doctor_obj, prefix = "doctoremail")

        qualification_formset = DoctorQualificationFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorqualification')

        hospital_formset = DoctorClinicFormSet(instance=doctor_obj, prefix='doctorclinic')
        language_formset = DoctorLanguageFormSet(data=request.POST, instance=doctor_obj, prefix = 'doctorlanguage')
        award_formset = DoctorAwardFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctoraward')
        association_formset = DoctorAssociationFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorassociation')
        experience_formset = DoctorExperienceFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctorexperience')
        #medicalservice_formset = DoctorServiceFormSet(data=request.POST, instance = doctor_obj, prefix = 'doctormedicalservice')

        validate_req = [mobile_formset, email_formset, qualification_formset, hospital_formset, language_formset, experience_formset]
        min_num = 0
        validate_min = False

        # if request.POST.get('_action',None) == '_submit':
        #     min_num = 1
        #     validate_min = True
        #     if 'awards_not_applicable' not in request.POST:
        #         validate_req.append(award_formset)
        #     if 'assoc_not_applicable' not in request.POST:
        #         validate_req.append(association_formset)

                # validate_req.append(association_formset)



        for x in validate_req:
            x.min_num = min_num
            x.validate_min = validate_min

        if not all([doctor_form.is_valid(), mobile_formset.is_valid(), email_formset.is_valid(), qualification_formset.is_valid()
                       , language_formset.is_valid(), award_formset.is_valid(),
            association_formset.is_valid(), experience_formset.is_valid()]):

            doc_images = DoctorImage.objects.filter(doctor=doctor_obj)

            doc_dict = OrderedDict()
            for id, value in DoctorDocument.CHOICES:
                results = DoctorDocument.objects.filter(doctor=doctor_obj, document_type=id)
                if len(results)>0:
                    doc_dict[id] = (id, value, results)
                else:
                    doc_dict[id] = (id, value, None)

            return render(request, 'onboard/doctor.html', {'doctor_form': doctor_form,
                'mobile_formset': mobile_formset,
                'email_formset': email_formset,
                'qualification_formset': qualification_formset,
                'hospital_formset': hospital_formset,
                'hospitaltiming_formset': hospitaltiming_formset,
                'language_formset': language_formset,
                'award_formset': award_formset,
                'association_formset': association_formset,
                'experience_formset': experience_formset,
                # 'medicalservice_formset': medicalservice_formset,
                'error_message' : 'Please fill all required fields',
                'doc_images' : doc_images,
                'doc_dict' :doc_dict,
                'DoctorDocument' : DoctorDocument
            })

        doc_obj = doctor_form.save()

        mobile_formset.save()
        email_formset.save()
        qualification_formset.save()
        # hospital_formset.save()
        try:
            language_formset.save()
        except:
            pass
        award_formset.save()
        association_formset.save()
        experience_formset.save()

        request.session['message'] = 'Successfully Saved Draft'

        action = request.POST.get('_action',None)

        if action=='_submit':
            instance.onboarding_status = Doctor.ONBOARDED
            instance.onboarded_at = datetime.datetime.now()
            instance.save()
            DoctorOnboardingToken.objects.filter(token = token).update(status=DoctorOnboardingToken.CONSUMED)


        return redirect("/onboard/doctor?token="+token, permanent=False)


def otp(request):

    token = request.GET.get('token')

    if not token:
        #return HttpResponse('Invalid URL. Token is required')
        return render(request,'onboard/access_denied.html')


    existing = None

    try:
        existing = DoctorOnboardingToken.objects.filter(token=token).order_by('-created_at')[0]
    except:
        pass

    if not existing:
        return render(request,'onboard/access_denied.html')

    if not existing.doctor:
        return render(request,'onboard/access_denied.html')


    if existing.status != DoctorOnboardingToken.GENERATED:
        return render(request,'onboard/access_denied.html')

    auth = request.session.get(token, False)
    if auth:
        return redirect("/onboard/doctor?token="+token, permanent=False)


    if request.method == 'POST':
        action = request.POST.get('_resend_otp')
        if action:
            otp = randint(200000, 900000)
            message = 'You have initiated onboarding process on DocPrime for '+existing.doctor.name+'. WELCOME CODE is '+str(otp)
            api.send_sms(message, str(existing.doctor.mobiles.filter(is_primary=True)[0].number))

            # email_message = '''Dear Sir/Mam,
            #     \n\nPlease find below the OTP for Onboarding Process:-
            #     \n\nOTP: %d''' % otp

            # primary_email = existing.doctor.emails.filter(is_primary=True).first()
            # if primary_email:
            #     try:
            #         email_api.send_email(primary_email, 'Onboarding OTP ', email_message)
            #     except Exception as e:
            #         logger.error(str(e))

            # print(otp)
            request.session['otp'] = otp
            request.session['otp_resent'] = True
            # request.session['otp_verified'] = True
            return redirect("/onboard/doctor/otp?token="+token, permanent=False)
        else:
            stored_otp = str(request.session.get('otp',''))
            otp = request.POST.get('otp')
            if otp == stored_otp:
                request.session[token] = True
                request.session["token_value"] = token
                return redirect("/onboard/doctor?token=" + token, permanent=False)
            else:
                request.session['otp_mismatch'] = True
                return redirect("/onboard/doctor/otp?token="+token, permanent=False)
    else:
        otp_resent = request.session.get('otp_resent', False)
        otp_mismatch = request.session.get('otp_mismatch', False)
        request.session['otp_resent'] = False
        request.session['otp_mismatch'] = False
        existingOTP = request.session.get('otp',None)

        label = 'Verify your Registered Mobile Number '+str(existing.doctor.mobiles.filter(is_primary=True)[0].number)
        page = 'otp_request'

        if existingOTP:
            page = 'otp_verify'
            label = '6 Digit verification code has been send to your mobile number '+str(existing.doctor.mobiles.filter(is_primary=True)[0].number)

    return render(request,'onboard/otp.html',{'label':label, 'page':page, 'otp_resent':otp_resent, 'otp_mismatch':otp_mismatch})
