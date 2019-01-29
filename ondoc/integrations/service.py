import requests
import logging
from rest_framework import status
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
import json
from .models import IntegratorMapping
from ondoc.integrations.Integrators import Thyrocare
from .Integrators import integrator_mapping


def create_integrator_obj(class_name):
    class_refrence = integrator_mapping[class_name]
    integrator_obj = class_refrence()
    return integrator_obj











