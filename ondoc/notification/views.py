from django.shortcuts import render, redirect, HttpResponse
from django.views import View
from django.template import Context, Template
from ondoc.notification.models import DynamicTemplates, RecipientEmail, NotificationAction
from django.utils.safestring import mark_safe


class DynamicTemplate(View):

    def get_invalid_content(self):
        content = '<p>Invalid Template</p>'
        t = Template(content)
        c = Context({})
        html = t.render(c)
        return html

    def get(self, request, template_name):
        obj = DynamicTemplates.objects.filter(template_name=template_name).first()

        if not obj:
            return HttpResponse(self.get_invalid_content())

        recipient_obj = RecipientEmail("akusaini@gmail.com").add_cc(['akashs@docprime.com']).add_bcc(['akusaini@gmail.com'])
        obj.send_notification({}, recipient_obj, NotificationAction.APPOINTMENT_ACCEPTED)

        # context = obj.get_content()
        # file_content = obj.content
        # t = Template(file_content)
        # c = Context(context)
        # html = t.render(c)
        return HttpResponse()
