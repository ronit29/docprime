from django.core.mail import send_mail

def send_email(to, sender, subject, message):
    send_mail('Subject here', 'Here is the message', 'arun@panaceatechno.com', ['arunchaudhary@policybazaar.com'], fail_silently=False)