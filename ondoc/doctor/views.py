from django.shortcuts import get_object_or_404
from .models import DoctorImage
from django.http import JsonResponse
import base64
from django.core.files.base import ContentFile


def crop_doctor_image(request):
    if request.method == "POST":
        doctor_image_id = request.POST.get('image_id')
        doctor_image = get_object_or_404(DoctorImage, pk=doctor_image_id)
        image_data = request.POST['data']
        format, imgstr = image_data.split(';base64,')
        data = ContentFile(base64.b64decode(imgstr))
        doctor_image.save_to_cropped_image(data)
        return JsonResponse({'success': 1})
    else:
        return JsonResponse({'success': 0})

