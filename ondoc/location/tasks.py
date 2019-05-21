from __future__ import absolute_import, unicode_literals
from celery import task
import logging

logger = logging.getLogger(__name__)

@task()
def update_profile_urls():
    from ondoc.location.models import UrlsModel
    UrlsModel.update_profile_urls()
    return True