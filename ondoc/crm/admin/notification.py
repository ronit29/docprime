from reversion.admin import VersionAdmin
from ondoc.notification.models import DynamicTemplates
from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


class EmailNotificationAdmin(VersionAdmin):
    list_display = ('user', 'notification_type', 'email', )
    search_fields = ('user', 'notification_type', )


class SmsNotificationAdmin(VersionAdmin):
    list_display = ('user', 'notification_type', 'phone_number', )
    search_fields = ('user', 'notification_type', )


class PushNotificationAdmin(VersionAdmin):
    list_display = ('user', 'notification_type', )
    search_fields = ('user', 'notification_type', )


class AppNotificationAdmin(VersionAdmin):
    list_display = ('user', 'notification_type', )
    search_fields = ('user', 'notification_type', )


class DynamicTemplateForm(forms.ModelForm):

    subject = forms.CharField(required=False)
    recipient = forms.CharField(required=False, help_text="Email address or mobile number according to the template type.")
    cc = forms.CharField(max_length=512, required=False, help_text="Email which needs to be in the cc. Please provide comma (,) seperated emails.")
    bcc = forms.CharField(max_length=512, required=False, help_text="Email which needs to be in the bcc. Please provide comma (,) seperated emails.")

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        if cleaned_data.get('template_type') == DynamicTemplates.TemplateType.EMAIL and not cleaned_data.get('subject'):
            raise forms.ValidationError('Subject is required for email templates.')

        recipient_address = cleaned_data.get('recipient')

        if recipient_address:
            if cleaned_data.get('template_type') == DynamicTemplates.TemplateType.SMS:

                if len(recipient_address) != 10:
                    raise forms.ValidationError("Invalid recipient Number")

                try:
                    int(recipient_address)
                except:
                    raise forms.ValidationError("Invalid recipient Number")

            elif cleaned_data.get('template_type') == DynamicTemplates.TemplateType.EMAIL:
                emails_list = []
                if cleaned_data.get('cc'):
                    emails_list.extend(cleaned_data.get('cc').split(','))
                if cleaned_data.get('bcc'):
                    emails_list.extend(cleaned_data.get('bcc').split(','))

                emails_list.append(recipient_address)

                try:
                    for email in emails_list:
                        validate_email(email)
                except ValidationError as e:
                    raise forms.ValidationError('Invalid email address in recipient or cc or bcc.')

        return cleaned_data


class DynamicTemplatesAdmin(VersionAdmin):
    form = DynamicTemplateForm
    model = DynamicTemplates
    list_display = ('template_type', 'template_name', 'preview_url')
    fields = ('template_type', 'subject', 'template_name', 'content', 'sample_parameters', 'recipient', 'cc', 'bcc', 'approved')

    def save_model(self, request, obj, form, change):
        responsible_user = request.user
        obj.created_by = responsible_user if responsible_user and not responsible_user.is_anonymous else None

        super().save_model(request, obj, form, change)
