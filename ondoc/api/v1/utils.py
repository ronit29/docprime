from rest_framework.views import exception_handler
from rest_framework import permissions
from collections import defaultdict
from operator import itemgetter
from itertools import groupby
from django.db import connection
from django.db.models import F, Func
from django.utils import timezone
import math
import datetime
import pytz
import calendar
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from ondoc.account.tasks import refund_curl_task
from ondoc.crm.constants import constants
import copy
import requests
import json
import random
import string
from django.conf import settings
from dateutil.parser import parse
from dateutil import tz
from django.utils.dateparse import parse_datetime
User = get_user_model()


def flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten_dict(value).items():
                    yield subkey, subvalue
            else:
                yield key, value

    return dict(items())


def first_error_only(d):
    code_mapping = {'min_value':'invalid', 'max_value':'invalid','invalid_choice':'invalid', 'null':'required'}

    new_dict = {}
    for key, value in d.items():
        if isinstance(value, (list,)) and value:
            new_dict[key] = value[0]
            new_dict[key]['code'] = code_mapping.get(new_dict[key]['code'],new_dict[key]['code'])

    return new_dict


def formatted_errors(dic):
    return first_error_only(flatten_dict(dic))


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    # Now add the HTTP status code to the response.
    if response is not None:
        try:
            data = formatted_errors(exc.get_full_details())
            nfe = data.get('non_field_errors')
            if nfe:
                del data['non_field_errors']
                data['request_errors'] = nfe

            response.data = data
        except Exception:
            pass

    return response


def group_consecutive_numbers(data):
    ranges = []
    for k, g in groupby(enumerate(data), lambda x: x[0] - x[1]):
        group = list(map(itemgetter(1), g))
        ranges.append((group[0], group[-1]))
    return ranges


def convert_timings(timings, is_day_human_readable=True):
    from ondoc.doctor.models import DoctorClinicTiming
    if not is_day_human_readable:
        DAY_MAPPING = {value[0]: (value[0], value[1][:3]) for value in DoctorClinicTiming.DAY_CHOICES}
    else:
        DAY_MAPPING = {value[1]: (value[0], value[1][:3]) for value in DoctorClinicTiming.DAY_CHOICES}
    DAY_MAPPING_REVERSE = {value[0]: value[1][:3] for value in DoctorClinicTiming.DAY_CHOICES}
    TIMESLOT_MAPPING = {value[0]: value[1] for value in DoctorClinicTiming.TIME_CHOICES}
    temp = defaultdict(list)
    for timing in timings:
        temp[(timing.get('start'), timing.get('end'))].append(DAY_MAPPING.get(timing.get('day')))
    for key, value in temp.items():
        temp[key] = sorted(value, key=itemgetter(0))
    final_dict = defaultdict(list)
    for key, value in temp.items():
        grouped_consecutive_days = group_consecutive_numbers(map(lambda x: x[0], value))
        response_keys = []
        for days in grouped_consecutive_days:
            if days[0] == days[1]:
                response_keys.append(DAY_MAPPING_REVERSE.get(days[0]))
            else:
                response_keys.append("{}-{}".format(DAY_MAPPING_REVERSE.get(days[0]),
                                                    DAY_MAPPING_REVERSE.get(days[1])))
        final_dict[",".join(response_keys)].append("{} to {}".format(TIMESLOT_MAPPING.get(key[0]),
                                                                     TIMESLOT_MAPPING.get(key[1])))
    return final_dict


def clinic_convert_timings(timings, is_day_human_readable=True):
    from ondoc.doctor.models import DoctorClinicTiming
    if not is_day_human_readable:
        DAY_MAPPING = {value[0]: (value[0], value[1][:3]) for value in DoctorClinicTiming.DAY_CHOICES}
    else:
        DAY_MAPPING = {value[1]: (value[0], value[1][:3]) for value in DoctorClinicTiming.DAY_CHOICES}
    DAY_MAPPING_REVERSE = {value[0]: value[1][:3] for value in DoctorClinicTiming.DAY_CHOICES}
    TIMESLOT_MAPPING = {value[0]: value[1] for value in DoctorClinicTiming.TIME_CHOICES}
    temp = defaultdict(list)
    for timing in timings:
        temp[(timing.start, timing.end)].append(DAY_MAPPING.get(timing.day))
    for key, value in temp.items():
        temp[key] = sorted(value, key=itemgetter(0))
    final_dict = defaultdict(list)
    for key, value in temp.items():
        grouped_consecutive_days = group_consecutive_numbers(map(lambda x: x[0], value))
        response_keys = []
        for days in grouped_consecutive_days:
            if days[0] == days[1]:
                response_keys.append(DAY_MAPPING_REVERSE.get(days[0]))
            else:
                response_keys.append("{}-{}".format(DAY_MAPPING_REVERSE.get(days[0]),
                                                    DAY_MAPPING_REVERSE.get(days[1])))
        final_dict[",".join(response_keys)].append("{} to {}".format(TIMESLOT_MAPPING.get(key[0]),
                                                                     TIMESLOT_MAPPING.get(key[1])))
    return final_dict

class RawSql:
    def __init__(self, query):
        self.query = query

    def fetch_all(self):
        with connection.cursor() as cursor:
            cursor.execute(self.query)
            columns = [col[0] for col in cursor.description]
            result = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        return result


class AgreedPriceCalculate(Func):
    function = 'labtest_agreed_price_calculate'


class DealPriceCalculate(Func):
    function = 'labtest_deal_price_calculate'


def form_time_slot(timestamp, time):
    to_zone = tz.gettz(settings.TIME_ZONE)
    min, hour = math.modf(time)
    min *= 60
    dt_field = timestamp.astimezone(to_zone).replace(hour=int(hour), minute=int(min), second=0, microsecond=0)
    return dt_field


def get_previous_month_year(month, year):
    dt = "01" + str(month) + str(year)
    dt = datetime.datetime.strptime(dt, "%d%m%Y")
    prev_dt = dt - datetime.timedelta(days=1)
    return prev_dt.month, prev_dt.year


def get_start_end_datetime(month, year, local_dt=None):
    now = timezone.now()
    if local_dt is not None:
        local_dt = timezone.localtime(now)
    else:
        dt = "01" + str(month) + str(year)
        dt = datetime.datetime.strptime(dt, "%d%m%Y")
        local_timezone = timezone.get_default_timezone().__str__()
        dt = pytz.timezone(local_timezone).localize(dt)
        local_dt = timezone.localtime(dt)
    start_dt = local_dt.replace(hour=0, minute=0, second=0, microsecond=0, day=1)
    end_dt = get_last_date_time(local_dt)
    return start_dt, end_dt


def get_last_date_time(dt):
    t, last_date = calendar.monthrange(dt.year, dt.month)
    return dt.replace(hour=23, minute=59, second=59, microsecond=0, day=last_date)


class IsConsumer(permissions.BasePermission):
    message = 'Consumer is allowed to perform action only.'

    def has_permission(self, request, view):
        if request.user.user_type == User.CONSUMER:
            return True
        return False


class IsDoctor(permissions.BasePermission):
    message = 'Doctor is allowed to perform action only.'

    def has_permission(self, request, view):
        if request.user.user_type == User.DOCTOR:
            return True
        return False


class IsNotAgent(permissions.BasePermission):
    message = 'Agent is not allowed to perform this action.'

    def has_permission(self, request, view):
        if hasattr(request, 'agent') and request.agent is not None:
            return False
        return True


class IsMatrixUser(permissions.BasePermission):
    message = 'Only Matrix User is allowed to Perform Action.'

    def has_permission(self, request, view):
        token = request.META.get('HTTP_MATRIX_AUTHORIZATION', None)
        if token is not None:
            if token == settings.MATRIX_AUTH_TOKEN:
                return True
        return False


def opdappointment_transform(app_data):
    """A serializer helper to serialize OpdAppointment data"""
    app_data["deal_price"] = str(app_data["deal_price"])
    app_data["fees"] = str(app_data["fees"])
    app_data["effective_price"] = str(app_data["effective_price"])
    app_data["mrp"] = str(app_data["mrp"])
    app_data["time_slot_start"] = str(app_data["time_slot_start"])
    app_data["doctor"] = app_data["doctor"].id
    app_data["hospital"] = app_data["hospital"].id
    app_data["profile"] = app_data["profile"].id
    app_data["user"] = app_data["user"].id
    app_data["booked_by"] = app_data["booked_by"].id
    return app_data


def labappointment_transform(app_data):
    app_data["price"] = str(app_data["price"])
    app_data["agreed_price"] = str(app_data["agreed_price"])
    app_data["deal_price"] = str(app_data["deal_price"])
    app_data["effective_price"] = str(app_data["effective_price"])
    app_data["time_slot_start"] = str(app_data["time_slot_start"])
    app_data["lab"] = app_data["lab"].id
    app_data["user"] = app_data["user"].id
    app_data["profile"] = app_data["profile"].id
    app_data["home_pickup_charges"] = str(app_data.get("home_pickup_charges",0))
    return app_data


def refund_curl_request(req_data):
    for data in req_data:
        refund_curl_task.apply_async((data, ), countdown=1)
        # refund_curl_task.delay(data)


def custom_form_datetime(time_str, to_zone, diff_days=0):
    next_dt = timezone.now().replace(tzinfo=to_zone).date()
    if diff_days:
        next_dt += datetime.timedelta(days=diff_days)
    exp_dt = str(next_dt) + " " + time_str
    exp_dt = parse(exp_dt).replace(tzinfo=to_zone)

    return exp_dt

class ErrorCodeMapping(object):
    IVALID_APPOINTMENT_ORDER = 1


def is_valid_testing_data(user, doctor):

    if doctor.is_test_doctor and not user.groups.filter(name=constants['TEST_USER_GROUP']).exists():
        return False
    return True


def is_valid_testing_lab_data(user, lab):

    if lab.is_test_lab and not user.groups.filter(name=constants['TEST_USER_GROUP']).exists():
        return False
    return True


def payment_details(request, order):
    from ondoc.authentication.models import UserProfile
    from ondoc.account.models import PgTransaction, Order
    payment_required = True
    user = request.user
    if user.email:
        uemail = user.email
    else:
        uemail = "dummyemail@docprime.com"
    base_url = "https://{}".format(request.get_host())
    surl = base_url + '/api/v1/user/transaction/save'
    furl = base_url + '/api/v1/user/transaction/save'
    profile = UserProfile.objects.get(pk=order.action_data.get("profile"))
    pgdata = {
        'custId': user.id,
        'mobile': user.phone_number,
        'email': uemail,
        'productId': order.product_id,
        'surl': surl,
        'furl': furl,
        'referenceId': "",
        'orderId': order.id,
        'name': profile.name,
        'txAmount': str(order.amount),
    }
    secret_key = client_key = ""
    if order.product_id == Order.DOCTOR_PRODUCT_ID:
        secret_key = settings.PG_SECRET_KEY_P1
        client_key = settings.PG_CLIENT_KEY_P1
    elif order.product_id == Order.LAB_PRODUCT_ID:
        secret_key = settings.PG_SECRET_KEY_P2
        client_key = settings.PG_CLIENT_KEY_P2
    elif order.product_id == Order.INSURANCE_PRODUCT_ID:
        secret_key = settings.PG_SECRET_KEY_P3
        client_key = settings.PG_CLIENT_KEY_P3

    pgdata['hash'] = PgTransaction.create_pg_hash(pgdata, secret_key, client_key)

    return pgdata, payment_required


def get_location(lat, long):
    pnt = None
    if long and lat:
        point_string = 'POINT(' + str(long) + ' ' + str(lat) + ')'
        pnt = GEOSGeometry(point_string, srid=4326)
    return pnt


def get_time_delta_in_minutes(last_visit_time):
    minutes = None
    time_format = '%Y-%m-%d %H:%M:%S'
    current_time_string = datetime.datetime.strftime(datetime.datetime.now(), time_format)
    last_time_object = datetime.datetime.strptime(last_visit_time, time_format)
    current_object = datetime.datetime.strptime(current_time_string, time_format)
    delta = current_object - last_time_object
    #print(delta)
    #if delta:
    minutes = delta.seconds / 60
    return minutes


def aware_time_zone(date_time_field):
    date = timezone.localtime(date_time_field, pytz.timezone(settings.TIME_ZONE))
    return date


def resolve_address(address_obj):
    address_string = ""
    address_dict = dict()
    if not isinstance(address_obj, dict):
        address_dict = vars(address_dict)
    else:
        address_dict = address_obj

    if address_dict.get("address"):
        if address_string:
            address_string += ", "
        address_string += str(address_dict["address"])
    if address_dict.get("land_mark"):
        if address_string:
            address_string += ", "
        address_string += str(address_dict["land_mark"])
    if address_dict.get("locality"):
        if address_string:
            address_string += ", "
        address_string += str(address_dict["locality"])
    if address_dict.get("pincode"):
        if address_string:
            address_string += ", "
        address_string += str(address_dict["pincode"])

    return address_string


def generate_short_url(url):
    from ondoc.web import models as web_models
    random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(10)])
    tiny_url = web_models.TinyUrl.objects.filter(short_code=random_string).first()
    if tiny_url:
        return tiny_url
    tiny_url = web_models.TinyUrl.objects.create(original_url=url, short_code=random_string)
    return tiny_url.get_tiny_url()


def readable_status_choices(product):
    from ondoc.account.models import Order
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    status_choices = dict()
    if product == Order.DOCTOR_PRODUCT_ID:
        for k, v in OpdAppointment.STATUS_CHOICES:
            status_choices[k] = v
    elif product == Order.LAB_PRODUCT_ID:
        for k, v in LabAppointment.STATUS_CHOICES:
            status_choices[k] = v
    return status_choices


def get_lab_search_details(entity, req_params):
    params_dict = copy.deepcopy(req_params)
    if entity.get('location_json'):
            if entity.get('location_json').get('sublocality_longitude'):
                params_dict['long'] = entity.get('location_json').get('sublocality_longitude')
            elif entity.get('location_json').get('locality_longitude'):
                params_dict['long'] = entity.get('location_json').get('locality_longitude')

            if entity.get('location_json').get('sublocality_latitude'):
                params_dict['lat'] = entity.get('location_json').get('sublocality_latitude')
            elif entity.get('location_json').get('locality_latitude'):
                params_dict['lat'] = entity.get('location_json').get('locality_latitude')

    return params_dict


def doctor_query_parameters(entity_params, req_params):
    params_dict = copy.deepcopy(req_params)
    if entity_params.get("location_json"):
        if entity_params["location_json"].get("sublocality_latitude"):
            params_dict["latitude"] = entity_params["location_json"]["sublocality_latitude"]
        elif entity_params["location_json"].get("locality_latitude"):
            params_dict["latitude"] = entity_params["location_json"]["locality_latitude"]

        if entity_params["location_json"].get("sublocality_longitude"):
            params_dict["longitude"] = entity_params["location_json"]["sublocality_longitude"]
        elif entity_params["location_json"].get("locality_longitude"):
            params_dict["longitude"] = entity_params["location_json"]["locality_longitude"]
    if entity_params.get("specialization_id"):
        params_dict["specialization_ids"] = str(entity_params["specialization_id"])
    return params_dict


def form_pg_refund_data(refund_objs):
    from ondoc.account.models import PgTransaction
    pg_data = list()
    for data in refund_objs:
        if data.pg_transaction:
            params = {
                "user": str(data.user.id),
                "orderNo": str(data.pg_transaction.order_no),
                "orderId": str(data.pg_transaction.order_id),
                "refundAmount": str(data.refund_amount),
                "refNo": str(data.id),
            }
            secret_key = settings.PG_SECRET_KEY_REFUND
            client_key = settings.PG_CLIENT_KEY_REFUND
            params["checkSum"] = PgTransaction.create_pg_hash(params, secret_key, client_key)
            pg_data.append(params)
    return pg_data
