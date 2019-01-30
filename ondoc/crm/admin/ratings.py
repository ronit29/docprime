from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from import_export import fields, resources
from ondoc.ratings_review.models import ReviewActions, RatingsReview
from ondoc.diagnostic.models import LabAppointment, Lab
from ondoc.doctor.models import OpdAppointment, Doctor
from django import forms
from import_export.admin import ImportExportMixin, ImportExportActionModelAdmin


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


class ReviewComplimentsForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        if cleaned_data.get('rating_level') and (
                cleaned_data.get('rating_level') > 5 or cleaned_data.get('rating_level') < 1 or type(
                cleaned_data.get('rating_level')) == float):
            raise forms.ValidationError("invalid rating level")


class ReviewComplimentsAdmin(admin.ModelAdmin):
    form = ReviewComplimentsForm


class RatingsReviewResource(resources.ModelResource):

    type = fields.Field()
    compliments = fields.Field()

    def dehydrate_type(self, obj):
        if obj.appointment_type:
            return dict(obj.APPOINTMENT_TYPE_CHOICES)[obj.appointment_type]
        return ''

    def dehydrate_compliments(self, obj):
        compliments_string = ''
        if obj.compliment:
            c_list = obj.compliment.values_list('message', flat=True)
            compliments_string = (', ').join(c_list)
        return compliments_string

    class Meta:
        model = RatingsReview
        fields = ('id', 'type', 'appointment_id', 'ratings', 'review', 'compliments', 'updated_at')
        export_order = ('id', 'type', 'appointment_id', 'ratings', 'review', 'compliments', 'updated_at')


class RatingsReviewAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = RatingsReviewResource
    inlines = [ReviewActionsInLine]
    list_display = (['name', 'booking_id', 'appointment_type', 'ratings', 'moderation_status', 'updated_at'])
    readonly_fields = ['user', 'name', 'booking_id', 'appointment_type']
    fields = ('user', 'ratings', 'review', 'name', 'booking_id', 'appointment_type', 'compliment',
              'moderation_status', 'moderation_comments')
    list_filter = ('appointment_type', 'moderation_status', 'ratings')
    # form = RatingsReviewForm

    def get_queryset(self, request):
        doctors = Doctor.objects.filter(rating__isnull=False).all().distinct()
        labs = Lab.objects.filter(rating__isnull=False).all().distinct()
        self.docs = doctors
        self.labs = labs
        return super(RatingsReviewAdmin, self).get_queryset(request).select_related('content_type')

    def get_form(self, request, obj=None, **kwargs):
        form = super(RatingsReviewAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['compliment'].widget = forms.CheckboxSelectMultiple()
        return form

    def booking_id(self, instance):
        url = None
        if instance.content_type == ContentType.objects.get_for_model(Doctor):
            url = "/admin/doctor/opdappointment/" + str(instance.appointment_id) + "/change"

        elif instance.content_type == ContentType.objects.get_for_model(Lab):
            url = "/admin/diagnostic/labappointment/" + str(instance.appointment_id) + "/change"
        if url:
            response = mark_safe('''<a href='%s' target='_blank'>%s</a>''' % (url, instance.appointment_id))
            return response
        return ''

    def name(self, instance):
        if instance.content_type == ContentType.objects.get_for_model(Doctor):
            for doc in self.docs:
                if doc.id == instance.object_id:
                    return doc.name
        elif instance.content_type == ContentType.objects.get_for_model(Lab):
            for lab in self.labs:
                if lab.id == instance.object_id:
                    return lab.name

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
