from decimal import InvalidOperation
from flask import Request


def get_request_parameter(
    key: str, req: Request, json: bool = False, required: bool = False
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
            return None

    return values.get(key)


def get_auth_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and len(auth_header.split(" ")) > 0:
        token = auth_header.split(" ")[1]
        if token:
            return token
    raise Exception("Missing Authorization Token")
