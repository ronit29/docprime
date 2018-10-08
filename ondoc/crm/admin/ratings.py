from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from ondoc.ratings_review.models import ReviewActions, RatingsReview
from ondoc.diagnostic.models import LabAppointment, Lab
from ondoc.doctor.models import OpdAppointment, Doctor
from django import forms

class RatingsReviewForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        object_id = cleaned_data.get('object_id')
        content_type = cleaned_data.get('content_type', None)
        if content_type==ContentType.objects.get_for_model(Lab):
            lab = Lab.objects.filter(pk=object_id).first()
            if not lab:
                raise forms.ValidationError("Lab not found")
        elif content_type == ContentType.objects.get_for_model(Doctor):
            doc = Doctor.objects.filter(pk=object_id).first()
            if not doc:
                raise forms.ValidationError("Doctor not found")
        else:
            raise forms.ValidationError("invalid content type")






class ReviewActionsInLine(admin.TabularInline):
    model = ReviewActions
    extra = 0
    can_delete = True


class RatingsReviewAdmin(admin.ModelAdmin):
    inlines = [ReviewActionsInLine]
    list_display = (['name', 'appointment_type', 'content_type', 'object_id', 'ratings', 'updated_at'])
    readonly_fields = ['name']
    form = RatingsReviewForm

    def name(self, instance):
        if instance.content_type==ContentType.objects.get_for_model(Doctor):
            doc = Doctor.objects.filter(pk=instance.object_id).first()
            if doc:
                return doc.name
        elif instance.content_type==ContentType.objects.get_for_model(Lab):
            lab = Lab.objects.filter(pk=instance.object_id).first()
            if lab:
                return lab.name
            else:
                return None

        return ''

        # if instance.appoitnment_type:
        #     if instance.appoitnment_type == RatingsReview.LAB :
        #
        #         l1 = LabAppontment.objects.filter(pk=instance.appoitnment_id).first()
        #         if l1 is not None and l1.lab is not None:
        #             lab_name = l1.lab.name
        #             return str(lab_name)
        #     elif instance.appoitnment_type == RatingsReview.OPD:
        #         d1 = OpdAppointment.objects.filter(pk=instance.appoitnment_id)
        #         if d1.exists():
        #             d1=d1.first()
        #             doctor_name = d1.doctor.name
        #             return str(doctor_name)
        #
        # return None
