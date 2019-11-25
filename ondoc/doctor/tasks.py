
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
    from ondoc.api.v1.utils import RawSql

    # update doctor seo urls
    Doctor.update_doctors_seo_urls()

    # update hospital seo urls
    Hospital.update_hospital_seo_urls()

    # update lab seo urls()
    # Lab.update_labs_seo_urls()

    # update ipd_procedure urls
    IpdProcedure.update_ipd_seo_urls()

    # update labs, doctors and hospitals profile urls
    from ondoc.location.models import UrlsModel
    UrlsModel.update_profile_urls()
    # Truncate temp_url table
    RawSql('truncate table temp_url', []).execute()
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

@task()
def update_rc_super_user():
    from ondoc.provider.models import RocketChatSuperUser
    RocketChatSuperUser.update_rc_super_user()

@task()
def doctors_daily_schedule():
    from ondoc.doctor.models import Hospital, OpdAppointment, OfflineOPDAppointments
    from ondoc.authentication.models import GenericAdmin
    from ondoc.communications.models import SMSNotification
    from ondoc.notification.models import NotificationAction
    from django.conf import settings
    import datetime, json

    curr_date = datetime.datetime.now()

    offline_appointments = OfflineOPDAppointments.objects.select_related('hospital', 'user') \
                                                         .prefetch_related('hospital__manageable_hospitals',
                                                                           'user__patient_mobiles') \
                                                         .filter(time_slot_start__date=curr_date.date(),
                                                                 hospital__network_type=Hospital.NON_NETWORK_HOSPITAL,
                                                                 hospital__is_live=True) \
                                                         .exclude(status__in=[OfflineOPDAppointments.CANCELLED,
                                                                              OfflineOPDAppointments.COMPLETED]) \
                                                         .exclude(hospital__id__in=json.loads(settings.DAILY_SCHEDULE_EXCLUDE_HOSPITALS))

    docprime_appointments = OpdAppointment.objects.select_related('profile') \
                                                  .prefetch_related('hospital__manageable_hospitals') \
                                                  .filter(time_slot_start__date=curr_date.date(),
                                                          hospital__network_type=Hospital.NON_NETWORK_HOSPITAL,
                                                          hospital__is_live=True) \
                                                  .exclude(status__in=[OpdAppointment.CANCELLED,
                                                                       OpdAppointment.COMPLETED]) \
                                                  .exclude(hospital__id__in=json.loads(settings.DAILY_SCHEDULE_EXCLUDE_HOSPITALS))
    hospital_admins_dict = dict()
    hospital_admin_appointments_dict = dict()
    appointments_list = [*offline_appointments, *docprime_appointments]
    for appointment in appointments_list:
        if hasattr(appointment, 'profile'):
            patient_number = appointment.profile.phone_number
        else:
            patient_numbers = appointment.user.patient_mobiles.all()
            patient_number = patient_numbers[0] if patient_numbers else None
            for number in patient_numbers:
                if number.is_default:
                    patient_number = number
        for admin in appointment.hospital.manageable_hospitals.all():
            if (admin.super_user_permission) or \
                    (admin.permission_type == GenericAdmin.APPOINTMENT and
                     ((not admin.doctor) or (admin.doctor and appointment.doctor == admin.doctor))):
                if appointment.hospital not in hospital_admins_dict:
                    hospital_admins_dict[appointment.hospital] = {admin}
                else:
                    hospital_admins_dict[appointment.hospital].add(admin)
                hospital_admin_combo = str(appointment.hospital.id)+'-'+str(admin.id)
                if hospital_admin_combo not in hospital_admin_appointments_dict:
                    hospital_admin_appointments_dict[hospital_admin_combo] = {(appointment, patient_number)}
                else:
                    hospital_admin_appointments_dict[hospital_admin_combo].add((appointment, patient_number))

    for hospital in hospital_admins_dict:
        admins = hospital_admins_dict[hospital]
        sms_sent = list()
        for admin in admins:
            if admin.phone_number in sms_sent or not (int(admin.phone_number) >= 1000000000 and int(admin.phone_number) <= 9999999999):
                continue
            receiver = [{'user': None, 'phone_number': admin.phone_number}]
            hospital_admin_combo = str(hospital.id) + '-' + str(admin.id)
            appointments_and_numbers = hospital_admin_appointments_dict[hospital_admin_combo]
            if appointments_and_numbers:
                context = {
                    "curr_date": curr_date,
                    "hospital_name": hospital.name,
                    "no_of_appointments": len(appointments_and_numbers),
                    # "appointments_and_numbers": appointments_and_numbers
                }
                sms_notification = SMSNotification(notification_type=NotificationAction.OPD_DAILY_SCHEDULE, context=context)
                sms_notification.send(receiver)
                sms_sent.append(admin.phone_number)

@task()
def fetch_place_ids():
    from ondoc.common.models import GoogleLatLong
    GoogleLatLong.generate_place_ids()