from model_import import ClientSDR
from flask import request, jsonify
from functools import wraps

def require_user(f):
    """ Decorator to check if the request has a valid token.

    Args:
        f (function): The function to be decorated.

    Returns:
        Any: The output of the decorated function, with the client_sdr_id as the first argument.
    """
    @wraps(f)
    def decorater(*args, **kwargs):
        token = None

        bearer_token = request.headers.get('Authorization')
        if bearer_token:
            if bearer_token.startswith('Bearer '):
                token = bearer_token.split(' ')[1]
            else:
                return jsonify({'message': 'Bearer token is missing.'}), 401
        else:
            return jsonify({'message': 'Authorization header is missing.'}), 401

        if not token:
            return jsonify({'message': 'Bearer token is missing.'}), 401

        try:
            sdr: ClientSDR = ClientSDR.query.filter_by(auth_token=token).first()
            sdr_id = sdr.id
        except AttributeError:
            return jsonify({'message': 'Authentication token is invalid.'}), 401

        return f(sdr_id, *args, **kwargs)
    return decorater


@require_user
def get_client_sdr_id(client_sdr_id: int):
    """A function to test the require_user decorator."""
    return client_sdr_id
