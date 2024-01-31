import os


def is_production():
    return (
        os.environ.get("APP_SETTINGS")
        == "config.ProductionConfig"
        # os.environ.get("FLASK_ENV") == "production"
        # or os.environ.get("FLASK_ENV") == "celery-production"
    )


def is_celery():
    return (
        os.environ.get("FLASK_ENV") == "celery-development"
        or os.environ.get("FLASK_ENV") == "celery-production"
    )


def is_scheduling_instance():
    return (
        os.environ.get("FLASK_ENV") == "production"
        and os.environ.get("SCHEDULING_INSTANCE") == "true"
    )
