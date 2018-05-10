from rest_framework.views import exception_handler


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
        data = formatted_errors(exc.get_full_details())
        response.data = data

    return response
