from rest_framework import serializers
from rest_framework.fields import CharField
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonTest, CommonDiagnosticCondition, LabImage, LabReportFile)
from django.contrib.staticfiles.templatetags.staticfiles import static
from ondoc.api.v1.auth.serializers import AddressSerializer, UserProfileSerializer
from ondoc.api.v1.utils import form_time_slot
from ondoc.doctor.models import OpdAppointment
from django.db.models import Count, Sum, When, Case, Q, F
from django.contrib.auth import get_user_model
from django.utils import timezone
from ondoc.api.v1 import utils
import datetime
import pytz
import random
import logging
import json


# class RatingsReviewCreateSerializer(serializers.Serializer):
