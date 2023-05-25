from decimal import InvalidOperation
from flask import Request
from typing import Optional


def get_request_parameter(
    key: str,
    req: Request,
    json: bool = False,
    required: bool = False,
    parameter_type: Optional[type] = None,
    default_value: Optional[any] = None,
) -> any:
    if json:
        values = req.get_json()
    else:
        values = req.values

    if values is None or key not in values:
        if required:
            message = "Invalid request. Required parameter `{}` missing.".format(key)
            raise InvalidOperation(message)
        else:
            return default_value

    value = values.get(key)
    if parameter_type == list and not json:
        value = values.getlist(key)
        if value[0] == '':
            return default_value
        value = value[0].split(',')
        return value
    if parameter_type != None and type(value) != parameter_type:
        message = "Invalid request. Parameter `{}` must be of type `{}` but was `{}`.".format(
            key, parameter_type, type(value)
        )
        raise InvalidOperation(message)

    return values.get(key, default_value)


def get_auth_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and len(auth_header.split(" ")) > 0:
        token = auth_header.split(" ")[1]
        if token:
            return token
    raise Exception("Missing Authorization Token")
