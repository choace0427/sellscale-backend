from functools import wraps

from flask import request as flask_request

_BODY_JSON = 'body_json'
_QUERY_PARAMS = 'query_params'
_MATCH_PARAMS = 'match_params'


def parse_flask_args(fn):
    @wraps(fn)
    def decorated_fn(*args, **kwargs):
        try:
            if (
                flask_request.headers.get('Content-Type')
                == 'application/x-www-form-urlencoded'
            ):
                body_json = dict(flask_request.form)
            else:
                body_json = flask_request.json or {}
        except:  # pylint:disable=bare-except
            body_json = {}

        query_params = dict(flask_request.args) or {}
        match_params = dict(flask_request.view_args) or {}
        kwargs.update(
            {
                _BODY_JSON: body_json,
                _QUERY_PARAMS: query_params,
                _MATCH_PARAMS: match_params,
            }
        )
        return fn(*args, **kwargs)

    return decorated_fn
