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
from ondoc.account.tasks import refund_curl_task
from ondoc.crm.constants import constants
import requests
import json
from django.conf import settings
from dateutil.parser import parse
from dateutil import tz
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
        refund_curl_task.delay(data)


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
    from ondoc.account.models import PgTransaction
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
    if hasattr(request, 'agent') and request.agent:
        pgdata["is_agent"] = True
    else:
        pgdata["is_agent"] = False

    pgdata['hash'] = PgTransaction.create_pg_hash(pgdata, settings.PG_SECRET_KEY_P1, settings.PG_CLIENT_KEY_P1)
    return pgdata, payment_required
