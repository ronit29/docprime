from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.shortcuts import render, redirect, HttpResponse

from ondoc.onboard.forms import LabImageForm, LabDocumentForm, DoctorImageForm, DoctorDocumentForm
from ondoc.diagnostic.models import LabImage, LabOnboardingToken, LabDocument
from ondoc.doctor.models import DoctorImage, DoctorOnboardingToken, DoctorDocument

class BasicUploadView(View):
    def get(self, request):
        pass


    def post(self, request):

        #token = request.session.get('token')
        token_value = request.session.get('token_value')
        if not token_value:
            return HttpResponse('Invalid URL')

        existing = None
        try:
            existing = LabOnboardingToken.objects.filter(token=token_value).order_by('-created_at')[0]
        except:
            pass

        media = request.POST.get('media')
        doc_type = request.POST.get('document_type')

        form = None
        if media == 'image':
            form = LabImageForm(self.request.POST, self.request.FILES)
        elif media == 'document':
            if int(doc_type) in [i[0] for i in LabDocument.CHOICES]:
                form = LabDocumentForm(self.request.POST, self.request.FILES)
            else:
                return HttpResponse(status=400)
        else:
            return HttpResponse(status=400)

        if form.is_valid() and existing and existing.lab:

            instance = form.save(commit=False)
            instance.lab = existing.lab
            instance.save()
            data = {'media_type':media, 'is_valid': True, 'url': instance.name.url, 'image_id':instance.id}
            return JsonResponse(data)
        else:
            return HttpResponse(status=400)

    def delete(self, request):
        token_value = request.session.get('token_value')
        image_type = request.GET.get('media_type')
        image_id = request.GET.get('image_id')
        if not token_value or not image_id or not image_type:
            return HttpResponse(status=400)

        existing = None
        try:
            existing = LabOnboardingToken.objects.filter(token=token_value).order_by('-created_at')[0]
        except:
            pass

        if not existing or not existing.lab:
            return HttpResponse(status=400)

        if image_type=='image':
            LabImage.objects.filter(lab=existing.lab, id=image_id).delete()
        elif image_type=='document':
            LabDocument.objects.filter(lab=existing.lab, id=image_id).delete()

        return JsonResponse({})





class DoctorUploadView(View):
    def get(self, request):
        pass


    def post(self, request):

        #token = request.session.get('token')
        token_value = request.session.get('token_value')
        if not token_value:
            return HttpResponse('Invalid URL')

        existing = None
        try:
            existing = DoctorOnboardingToken.objects.filter(token=token_value).order_by('-created_at')[0]
        except:
            pass

        media = request.POST.get('media')
        doc_type = request.POST.get('document_type')

        form = None
        if media == 'image':
            form = DoctorImageForm(self.request.POST, self.request.FILES)
        elif media == 'document':
            if int(doc_type) in [i[0] for i in DoctorDocument.CHOICES]:
                form = DoctorDocumentForm(self.request.POST, self.request.FILES)
            else:
                return HttpResponse(status=400)
        else:
            return HttpResponse(status=400)

        if form.is_valid() and existing and existing.doctor:

            instance = form.save(commit=False)
            instance.doctor = existing.doctor
            instance.save()
            data = {'media_type':media, 'is_valid': True, 'url': instance.name.url, 'image_id':instance.id}
            return JsonResponse(data)
        else:
            return HttpResponse(status=400)

    def delete(self, request):
        token_value = request.session.get('token_value')
        image_type = request.GET.get('media_type')
        image_id = request.GET.get('image_id')
        if not token_value or not image_id or not image_type:
            return HttpResponse(status=400)

        existing = None
        try:
            existing = DoctorOnboardingToken.objects.filter(token=token_value).order_by('-created_at')[0]
        except:
            pass

        if not existing or not existing.doctor:
            return HttpResponse(status=400)

        if image_type=='image':
            DoctorImage.objects.filter(doctor=existing.doctor, id=image_id).delete()
        elif image_type=='document':
            DoctorDocument.objects.filter(doctor=existing.doctor, id=image_id).delete()

        return JsonResponse({})

