from rest_framework import serializers
from collections import defaultdict
from rest_framework.fields import NullBooleanField
from rest_framework.renderers import JSONRenderer
from ondoc.diagnostic.models import Lab
from ondoc.doctor.models import Doctor

