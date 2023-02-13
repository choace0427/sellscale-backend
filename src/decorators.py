from model_import import ClientSDR
from flask import request, jsonify
from functools import wraps

def token_required(f):
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

        try:
            sdr: ClientSDR = ClientSDR.query.get(auth_token=token)
        except:
            return jsonify({'message': 'Authentication token is invalid.'}), 401

        return f(sdr, *args, **kwargs)
    return decorater
