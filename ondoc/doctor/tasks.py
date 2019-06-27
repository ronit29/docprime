
from __future__ import absolute_import, unicode_literals

from django.db import transaction
from celery import task
import logging

logger = logging.getLogger(__name__)


@task(bind=True)
@transaction.atomic
def doc_app_auto_cancel(self, prev_app_dict):
    from .models import OpdAppointment
    try:
        opd_status = [OpdAppointment.CANCELLED, OpdAppointment.COMPLETED, OpdAppointment.ACCEPTED, ]
        present_app_obj = OpdAppointment.objects.filter(pk=prev_app_dict.get("id")).first()
        if present_app_obj:
            if present_app_obj.status not in opd_status and prev_app_dict.get(
                    "status") == present_app_obj.status and int(prev_app_dict.get("updated_at")) == int(present_app_obj.updated_at.timestamp()):
                present_app_obj.cancellation_type = OpdAppointment.AUTO_CANCELLED
                present_app_obj.action_cancelled(refund_flag=1)
            else:
                logger.error("Error in Celery - Condition not satisfied for - " + str(prev_app_dict.get("id")) + " with prev status - " + str(prev_app_dict.get("status")) + " and present status - "+ str(present_app_obj.status) + " and prev updated time - "+ str(prev_app_dict.get("updated_at")) + " and present updated time - " + str(present_app_obj.updated_at))
        else:
            logger.error("Error in Celery - No opd appointment for - " + str(prev_app_dict.get("id")))
    except Exception as e:
        logger.error("Error in Celery auto cancel flow - " + str(e))


@task()
def save_avg_rating():
    from ondoc.doctor.models import Doctor, Hospital
    from ondoc.diagnostic.models import Lab
    Doctor.update_avg_rating()
    Lab.update_avg_rating()
    Hospital.update_avg_rating()


@task()
def update_prices():
    from ondoc.doctor.models import Doctor
    from ondoc.diagnostic.models import AvailableLabTest
    Doctor.update_all_deal_price()
    AvailableLabTest.update_all_deal_price()    
    return 'success'

@task
def update_city_search_key():
    from ondoc.doctor.models import Hospital
    Hospital.update_city_search()

@task
def update_doctors_count():
    from ondoc.doctor.services.doctor_count_in_practice_spec import DoctorSearchScore
    DoctorSearchScore.update_doctors_count()

@task
def update_search_score():
    from ondoc.doctor.services.update_search_score import DoctorSearchScore
    obj = DoctorSearchScore()
    obj.create_search_score()



@task
def update_all_ipd_seo_urls():
    from ondoc.procedure.models import IpdProcedure
    IpdProcedure.update_ipd_seo_urls()

@task
def update_insured_labs_and_doctors():
    from ondoc.doctor.models import Doctor
    from ondoc.diagnostic.models import Lab
    Doctor.update_insured_doctors()
    Lab.update_insured_labs()

@task
def update_seo_urls():
    from ondoc.doctor.models import Doctor, Hospital
    from ondoc.diagnostic.models import Lab
    from ondoc.procedure.models import IpdProcedure

    # update doctor seo urls
    Doctor.update_doctors_seo_urls()

    # update hospital seo urls
    Hospital.update_hospital_seo_urls()

    # update lab seo urls()
    Lab.update_labs_seo_urls()

    # update ipd_procedure urls
    IpdProcedure.update_ipd_seo_urls()

    # update labs, doctors and hospitals profile urls
    from ondoc.location.models import UrlsModel
    UrlsModel.update_profile_urls()
    return True


@task
def update_hosp_google_avg_rating():
    from ondoc.doctor.models import HospitalPlaceDetails, Hospital
    HospitalPlaceDetails.update_hosp_place_with_google_api_details()
    Hospital.update_hosp_google_avg_rating()


@task()
def update_flags():
    from ondoc.doctor.models import Hospital
    Hospital.update_is_big_hospital()


@task
def decrypted_invoice_pdfs(self, hospitals):
    from ondoc.doctor import models as doc_models

    version = '01'
    for hospital in hospitals:
        encrypted_invoices = doc_models.PartnersAppInvoice.objects.filter(appointment__hospital=hospital, is_encrypted=True, is_valid=True).order_by('updated_at')
        last_unencrypted_invoice = doc_models.PartnersAppInvoice.objects.filter(appointment__hospital=hospital, is_encrypted=False, is_valid=True).order_by('-created_at').first()
        serial = last_unencrypted_invoice.serial_id[-9:-3] + 1 if last_unencrypted_invoice else doc_models.PartnersAppInvoice.INVOICE_SERIAL_ID_START
        for invoice in encrypted_invoices:
            invoice.serial_id = serial
            invoice.serial_id = 'INV-' + str(invoice.appointment.hospital.id) + '-' + str(invoice.appointment.doctor.id) + '-' + str(serial) + '-' + version
            invoice.generate_invoice(invoice.selected_invoice_items, invoice.appointment)
            invoice.is_encrypted = False
            invoice.save()
            serial += 1
