# from django.core import mail
from django.core.mail import send_mail


def send_email(to, sender, subject, body):

    send_mail(
        'Subject here',
        'Here is the message.',
        'support@panaceatechno.com',
        ['arunchaudhary@policybazaar.com'],
        auth_user='policybazaarcom1',
        auth_password='Sm@pbzc3',
        fail_silently=False,
    )

    # with mail.get_connection() as connection:
    #     mail.EmailMessage(
    #         subject, body, sender, [to],
    #         connection=connection,
    #     ).send()

    print("Email sent")
