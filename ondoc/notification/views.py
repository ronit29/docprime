from django.shortcuts import render, redirect, HttpResponse
from django.views import View
from django.template import Context, Template
from ondoc.notification.models import DynamicTemplates, RecipientEmail, NotificationAction
from django.utils.safestring import mark_safe
from django.conf import settings


class DynamicTemplate(View):

    def get_invalid_content(self):
        content = '<p>Invalid Template</p>'
        t = Template(content)
        c = Context({})
        html = t.render(c)
        return html

    def get(self, request, template_name, *args, **kwargs):
        obj = DynamicTemplates.objects.filter(template_name=template_name).first()

        if not obj:
            return HttpResponse(self.get_invalid_content())

        if request.GET.get('send') == 'True':

            if obj.recipient:

                if obj.template_type == DynamicTemplates.TemplateType.EMAIL:
                    recipient_obj = RecipientEmail(obj.recipient).add_cc([]).add_bcc([])
                else:
                    recipient_obj = obj.recipient

                obj.send_notification(obj.get_parameter_json(), recipient_obj, NotificationAction.APPOINTMENT_ACCEPTED)
                html = "Notification send successfully."
            else:
                html = "Recipient Number or address found to send notification."

        else:

            html = obj.render_template(obj.get_parameter_json())

        return HttpResponse(html)
