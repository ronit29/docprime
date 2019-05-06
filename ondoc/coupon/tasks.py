from __future__ import absolute_import, unicode_literals

import copy
import datetime
import json
import math
import random
import string
import traceback
from collections import OrderedDict
from io import BytesIO

from django.db import transaction
from django.forms import model_to_dict
from django.utils import timezone
from openpyxl import load_workbook

from ondoc.api.v1.utils import aware_time_zone, util_absolute_url
from ondoc.common.models import AppointmentMaskNumber
from ondoc.notification.labnotificationaction import LabNotificationAction
from ondoc.notification import models as notification_models
from celery import task
import logging
from django.conf import settings
import requests
from rest_framework import status
from django.utils.safestring import mark_safe
from ondoc.notification.models import NotificationAction

logger = logging.getLogger(__name__)


@task
def generate_random_coupons(total_count, coupon_id):
    from ondoc.coupon.models import RandomGeneratedCoupon, Coupon
    try:
        coupon_obj = Coupon.objects.filter(id=coupon_id).first()
        if not coupon_obj:
            return

        while total_count:
            curr_count = 0
            batch_data = []
            while curr_count < 10000 and total_count:
                rc = RandomGeneratedCoupon()
                rc.random_coupon = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                rc.coupon = coupon_obj
                rc.validity = 90
                rc.sent_at = datetime.datetime.utcnow()

                batch_data.append(rc)
                curr_count += 1
                total_count -= 1

            if batch_data:
                RandomGeneratedCoupon.objects.bulk_create(batch_data)
            else:
                return

    except Exception as e:
        logger.error(str(e))

