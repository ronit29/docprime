from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.shortcuts import render, redirect, HttpResponse

from ondoc.onboard.forms import LabImageForm, LabDocumentForm
from ondoc.diagnostic.models import LabImage, LabOnboardingToken, LabDocument

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
        type = request.POST.get('document_type')

        form = None
        if media == 'image':
            form = LabImageForm(self.request.POST, self.request.FILES)
        elif media == 'document':
            if int(type) in [i[0] for i in LabDocument.CHOICES]:
                form = LabDocumentForm(self.request.POST, self.request.FILES)
            else:
                return HttpResponse(status=400)
        else:
            return HttpResponse(status=400)

        if form.is_valid() and existing and existing.lab:

            instance = form.save(commit=False)
            instance.lab = existing.lab
            instance.save()
            data = {'is_valid': True, 'url': instance.name.url}
            return JsonResponse(data)
        else:
            return HttpResponse(status=400)
