from model_import import ClientSDR
from flask import request, jsonify
from functools import wraps
import time


def rate_limit(max_calls, time_interval):
    """
    Decorator to limit the number of calls to a function from the same IP address
    within a certain time period.

    Args:
        max_calls (int): Maximum number of allowed calls.
        time_interval (float): Time interval in seconds.

    Returns:
        Decorated function.
    """
    call_times_per_ip = {}

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Get client IP address
            client_ip = request.remote_addr

            # Get current time
            current_time = time.time()

            # Initialize or update call times for this IP
            if client_ip not in call_times_per_ip:
                call_times_per_ip[client_ip] = []
            call_times_per_ip[client_ip] = [
                call_time
                for call_time in call_times_per_ip[client_ip]
                if current_time - call_time < time_interval
            ]

            # Check if max calls exceeded for this IP
            if len(call_times_per_ip[client_ip]) >= max_calls:
                return (
                    "Rate limit exceeded for your IP. Please wait before calling again."
                )

            # Call the function and update call times for this IP
            call_times_per_ip[client_ip].append(current_time)
            return f(*args, **kwargs)

        return wrapped

    return decorator


def require_user(f):
    """Decorator to check if the request has a valid token.

    Args:
        f (function): The function to be decorated.

    Returns:
        Any: The output of the decorated function, with the client_sdr_id as the first argument.
    """

    @wraps(f)
    def decorater(*args, **kwargs):
        token = None

        bearer_token = request.headers.get("Authorization")
        if bearer_token:
            if bearer_token.startswith("Bearer "):
                token = bearer_token.split(" ")[1]
            else:
                return jsonify({"message": "Bearer token is missing."}), 401
        else:
            return jsonify({"message": "Authorization header is missing."}), 401

        if not token:
            return jsonify({"message": "Bearer token is missing."}), 401

        try:
            sdr: ClientSDR = ClientSDR.query.filter_by(auth_token=token).first()
            sdr_id = sdr.id
        except AttributeError:
            return jsonify({"message": "Authentication token is invalid."}), 401

        return f(sdr_id, *args, **kwargs)

    return decorater


@require_user
def get_client_sdr_id(client_sdr_id: int):
    """A function to test the require_user decorator."""
    return client_sdr_id
