from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from import_export import fields, resources

from ondoc.authentication.models import AgentToken
from ondoc.provider import models as prov_models
# from ondoc.diagnostic.models import LabAppointment, Lab
# from ondoc.doctor.models import OpdAppointment, Doctor, Hospital
from django import forms
from django.conf import settings
from ondoc.api.v1 import utils as v1_utils
# from ondoc.notification import tasks as notification_tasks
from import_export.admin import ImportExportMixin, base_formats
import logging
logger = logging.getLogger(__name__)


class PartnerLabTestSampleDetailAdmin(admin.ModelAdmin):
    list_display = ('id', 'lab_test', 'sample')
    readonly_fields = []
    autocomplete_fields = ['lab_test', 'sample']


class PartnerLabTestSampleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at', 'updated_at')
    readonly_fields = []
    search_fields = ['name']


class TestSamplesLabAlertAdmin(admin.ModelAdmin):
    list_display = ('name', )