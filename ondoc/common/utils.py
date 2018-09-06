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
    message = {
        "data": locals(),
        "type": "email"
    }

    message = json.dumps(message)
    print(message)
    publish_message(message)


# send_email(["Bob_O'Reilly+tag@example.com"], subject='sub', content='c')
