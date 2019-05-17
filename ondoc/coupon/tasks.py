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


