from rest_framework.views import exception_handler
from collections import defaultdict
from operator import itemgetter
from itertools import groupby
from ondoc.doctor.models import DoctorHospital


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


def convert_timings(timings):
    DAY_MAPPING = {value[1]: (value[0], value[1][:3]) for value in DoctorHospital.DAY_CHOICES}
    DAY_MAPPING_REVERSE = {value[0]: value[1][:3] for value in DoctorHospital.DAY_CHOICES}
    TIMESLOT_MAPPING = {value[0]: value[1] for value in DoctorHospital.TIME_SLOT_CHOICES}
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
