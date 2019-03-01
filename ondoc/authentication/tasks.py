from __future__ import absolute_import, unicode_literals
from celery import task

@task()
def update_ben_status_from_pg():
    from ondoc.authentication.models import Merchant
    Merchant.update_status_from_pg()
    return "success"
