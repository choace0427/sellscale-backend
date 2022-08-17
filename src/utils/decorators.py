from functools import wraps
from flask import request
from src.auth.services import get_user_from_auth_token
from src.utils.request_helpers import get_auth_token, get_request_parameter



def require_valid_user(f=None, optional_param=False):
    """
    Only allow valid user to access
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = get_request_parameter(
            'user_id', request, json=True, required=True)

        token = get_auth_token(request)
        user = get_user_from_auth_token(token)

        if not user:
            raise Exception("Invalid auth token")

        if user.id != user_id:
            raise Exception("Invalid auth token + user combo")

        return f(*args, **kwargs)

    return decorated
