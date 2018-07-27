# from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from .models import Doctor, DoctorImage


# Create your views here.
def crop_doctor_image(request, doctor_id, image_id):
    required_doctor = get_object_or_404(Doctor, pk=doctor_id)
    required_doctor_image = get_object_or_404(required_doctor.images, pk=image_id)

    return render(request, 'doctor/crop_doctor_image.html', {'doctor_image': required_doctor_image})

