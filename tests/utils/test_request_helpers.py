from src.utils.random_string import *
from app import db
import mock
from src.utils.request_helpers import get_request_parameter, get_auth_token


def test_get_request_parameter():
    request = mock.Mock(values={"test": "value"})
    value = get_request_parameter(
        key="test",
        req=request,
        json=False,
        required=False,
    )

    assert value == "value"

    value = get_request_parameter(
        key="does_not_exist",
        req=request,
        json=False,
        required=False,
    )
    assert value == None

    raised_flag = False
    try:
        value = get_request_parameter(
            key="does_not_exist",
            req=request,
            json=False,
            required=True,
        )
    except Exception as e:
        raised_flag = True
    assert raised_flag == True

    raised_flag = False
    try:
        value = get_request_parameter(
            key="test",
            req=request,
            json=False,
            required=True,
            parameter_type=int,
        )
    except Exception as e:
        assert str(e) == "Invalid request. Parameter `test` must be of type `<class 'int'>` but was `<class 'str'>`."
        raised_flag = True
    assert raised_flag == True



def test_get_auth_token():
    request = mock.Mock(headers={"Authorization": "Bearer SAMPLE_TOKEN"})
    token = get_auth_token(request)
    assert token == "SAMPLE_TOKEN"
