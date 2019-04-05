from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from import_export import fields, resources

from ondoc.authentication.models import AgentToken
from ondoc.ratings_review.models import ReviewActions, RatingsReview
from ondoc.diagnostic.models import LabAppointment, Lab
from ondoc.doctor.models import OpdAppointment, Doctor, Hospital
from django import forms
from import_export.admin import ImportExportMixin, ImportExportActionModelAdmin
from django.conf import settings
from ondoc.api.v1 import utils as v1_utils
from ondoc.notification import tasks as notification_tasks
import logging
logger = logging.getLogger(__name__)


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


class RatingsReviewForm(forms.ModelForm):
    send_update_text = forms.CharField(initial='Please Find the url to Update your Feedback!', required=False)
    send_update_sms = forms.BooleanField(required=False)


class RatingVerificationFilter(admin.SimpleListFilter):
    title = "type"

    parameter_name = 'appointment_id'

    def lookups(self, request, model_admin):

        return (
            ('verified', 'Verified'),
            ('unverified', 'Unverified'),
        )

    def queryset(self, request, queryset):

        if self.value() == 'verified':
            return queryset.filter(appointment_id__isnull=False)

        if self.value() == 'unverified':
            return queryset.filter(appointment_id__isnull=True)


class RatingsReviewAdmin(ImportExportMixin, admin.ModelAdmin):
    form = RatingsReviewForm
    search_fields = ['appointment_id']
    resource_class = RatingsReviewResource
    inlines = [ReviewActionsInLine]
    list_display = (['name', 'booking_id', 'appointment_type', 'ratings', 'moderation_status', 'updated_at'])
    readonly_fields = ['user', 'name', 'booking_id', 'appointment_type']
    fields = ('user', 'ratings', 'review', 'name', 'booking_id', 'appointment_type', 'compliment',
              'moderation_status', 'moderation_comments', 'send_update_text', 'send_update_sms')
    list_filter = ('appointment_type', 'moderation_status', 'ratings', RatingVerificationFilter)
    # form = RatingsReviewForm

    def get_queryset(self, request):
        doctors = Doctor.objects.filter(rating__isnull=False).all().distinct()
        labs = Lab.objects.filter(rating__isnull=False).all().distinct()
        hospitals = Hospital.objects.filter(ratings__isnull=False).all().distinct()
        self.docs = doctors
        self.labs = labs
        # self.hospitals = hospitals
        return super(RatingsReviewAdmin, self).get_queryset(request).select_related('content_type').order_by('-appointment_id')

    def get_form(self, request, obj=None, **kwargs):
        form = super(RatingsReviewAdmin, self).get_form(request, obj, **kwargs)
        if obj:
            form.base_fields['compliment'].widget = forms.CheckboxSelectMultiple()
            type = obj.appointment_type
            if type == RatingsReview.HOSPITAL:
                type = RatingsReview.OPD
            form.base_fields['compliment'].queryset = form.base_fields['compliment'].queryset.filter(type=type)
        return form

    def booking_id(self, instance):
        url = None
        if not instance.appointment_id:
            return ''
        if instance.content_type == ContentType.objects.get_for_model(Doctor):
            url = "/admin/doctor/opdappointment/" + str(instance.appointment_id) + "/change"

        elif instance.content_type == ContentType.objects.get_for_model(Lab):
            url = "/admin/diagnostic/labappointment/" + str(instance.appointment_id) + "/change"
        if url:
            response = mark_safe('''<a href='%s' target='_blank'>%s</a>''' % (url, instance.appointment_id))
            return response
        return ''
    booking_id.admin_order_field = 'appointment_id'

    def send_update_sms(self, instance, msg):
        from ondoc.authentication.backends import JWTAuthentication
        if instance:
            if instance.user:
                # agent_token = AgentToken.objects.create_token(user=instance.user)
                agent_token = JWTAuthentication.generate_token(instance.user)
                token = agent_token['token'] if 'token' in agent_token else None
                url = settings.BASE_URL + "/myratings?id=" + str(instance.id) + "&token=" + token.decode("utf-8")
                short_url = v1_utils.generate_short_url(url)
                text = msg if msg else "Please Find the url to Update your Feedback "
                final_text = str(text) + ' ' + str(short_url)
                try:
                    notification_tasks.send_rating_update_message.apply_async(
                        kwargs={'number': instance.user.phone_number, 'text': final_text},
                        countdown=1)
                except Exception as e:
                    logger.error("Failed to send User Rating update message  " + str(e))


    def name(self, instance):
        if instance.content_type == ContentType.objects.get_for_model(Doctor):
            for doc in self.docs:
                if doc.id == instance.object_id:
                    return doc.name
        elif instance.content_type == ContentType.objects.get_for_model(Lab):
            for lab in self.labs:
                if lab.id == instance.object_id:
                    return lab.name
        # elif instance.content_type == ContentType.objects.get_for_model(Hospital):
        #     for hospital in self.hospitals:
        #         if hospital.id == instance.object_id:
        #             return hospital.name
        return ''

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get('send_update_sms'):
            text = form.cleaned_data['send_update_text'] if form.cleaned_data.get('send_update_text') else None
            self.send_update_sms(obj, text)
        moderation_status = form.cleaned_data.get('moderation_status')
        if moderation_status == RatingsReview.DENIED:
            obj.is_live = False
        elif moderation_status == RatingsReview.APPROVED:
            obj.is_live = True
        elif moderation_status == RatingsReview.PENDING:
            obj.is_live = True if obj.appointment_id else False
        super().save_model(request, obj, form, change)

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
