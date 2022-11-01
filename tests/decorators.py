from test_utils import test_app


def use_app_context(func):
    def wrapper_func(test_app):
        with test_app.app_context():
            func()

    return wrapper_func
