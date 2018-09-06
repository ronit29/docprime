import json
import re
from ondoc.notification.rabbitmq_client import publish_message


def all_emails(items):
    email_regex = re.compile(r"[^@]+@[^@]+\.[^@]+")
    return all(email_regex.match(item) for item in items)


def send_email(to=[], cc=[], subject=None, content=None):
    """

    :param to:
    :param cc:
    :param subject:
    :param content:
    :return:
    """
    assert to and isinstance(to, list) and len(to) > 0 and all_emails(to), 'to must be a non-empty list of emails'
    assert isinstance(cc, list) and all_emails(cc), 'cc must be a list of emails'
    assert subject and isinstance(subject, str), 'subject must be a non-empty string'
    assert content and isinstance(content, str), 'content must be a non-empty string'
    for email in to:
        message = {
            "data": {
                "content": content,
                "email": email,
                "cc": cc,
                "email_subject": subject
            },
            "type": "email"
        }

        message = json.dumps(message)
        print(message)
        publish_message(message)


# send_email(["Bob_O'Reilly+tag@example.com"], subject='sub', content='c')

def send_sms(text, phone_number=[]):
    assert text and isinstance(text, str), 'text must be a non-empty string'
    assert phone_number and isinstance(phone_number, list), 'phone_number must be a non-empty list'
    for number in phone_number:
        message = {
            "data": {
                "phone_number": number,
                "content": text
            },
            "type": "sms"
        }
        message = json.dumps(message)
        publish_message(message)




