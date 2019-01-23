from rest_framework import serializers
from rest_framework.fields import CharField
from django.db.models import Q, Avg, Count, Max
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from ondoc.api.v1.utils import is_valid_testing_data, form_time_slot, GenericAdminEntity
from django.contrib.auth import get_user_model
import math, datetime, logging
from django.conf import settings


logger = logging.getLogger(__name__)

User = get_user_model()


