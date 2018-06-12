from django.core.mail import send_mail

def send_email(to, subject, message):
    # send_mail(subject, message, 'arun@policybazaar.com', [to], fail_silently=False)
    send_mail(subject, message, 'support@docprime.com', [to], fail_silently=False)