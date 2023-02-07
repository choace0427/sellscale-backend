import os

from kombu import Queue, Exchange
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy

from flask_cors import CORS
from flask_migrate import Migrate

from flask_sqlalchemy import SQLAlchemy
from src.setup.TimestampedModel import TimestampedModel
from src.utils.scheduler import *
from src.utils.slack import URL_MAP

from celery import Celery
from src.utils.slack import send_slack_message


def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=app.config["CELERY_BROKER_URL"],
    )
    celery.conf.update(app.config)

    celery.conf.broker_transport_options = {
        'queue_order_strategy': 'priority',
    }

    default_exchange = Exchange('default', type='direct')
    prospecting_exchange = Exchange('prospecting', type='direct')
    celery.conf.task_queues = (
        Queue('default', default_exchange, routing_key='default'),
        Queue('prospecting', prospecting_exchange, routing_key='prospecting'),
    )
    celery.conf.task_default_queue = 'default'
    celery.conf.task_default_exchange = 'default'
    celery.conf.task_default_routing_key = 'default'
    celery.conf.task_default_priority = 5               # 0 is the highest

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


app = Flask(__name__)
app.config.update(
    CELERY_BROKER_URL=os.environ.get("CELERY_REDIS_URL"),
)
celery = make_celery(app)
cors = CORS(app)

app.config["CORS_HEADERS"] = "Content-Type"

app.config.from_object(os.environ["APP_SETTINGS"])
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(model_class=TimestampedModel)
migrate = Migrate(app, db)

from model_import import *


@celery.task()
def add_together(a, b):
    from datetime import datetime

    send_slack_message(
        message="Testing from slack!" + str(datetime.utcnow()),
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )
    return a + b


def register_blueprints(app):
    from src.echo.controllers import ECHO_BLUEPRINT
    from src.prospecting.controllers import PROSPECTING_BLUEPRINT
    from src.research.controllers import RESEARCH_BLUEPRINT
    from src.client.controllers import CLIENT_BLUEPRINT
    from src.message_generation.controllers import MESSAGE_GENERATION_BLUEPRINT
    from src.ml.controllers import ML_BLUEPRINT
    from src.automation.controllers import AUTOMATION_BLUEPRINT
    from src.analytics.controllers import ANALYTICS_BLUEPRINT
    from src.email_outbound.controllers import EMAIL_GENERATION_BLUEPRINT
    from src.campaigns.controllers import CAMPAIGN_BLUEPRINT
    from src.sight_inbox.controllers import SIGHT_INBOX_BLUEPRINT
    from src.editing_tools.controllers import EDITING_TOOLS_BLUEPRINT
    from src.response_ai.controllers import RESPONSE_AI_BLUEPRINT
    from src.onboarding.controllers import ONBOARDING_BLUEPRINT
    from src.ml_adversary.controllers import ML_ADVERSARY_BLUEPRINT
    from src.editor.controllers import EDITOR_BLUEPRINT
    from src.li_conversation.controllers import LI_CONVERASTION_BLUEPRINT
    from src.daily_notifications.controllers import DAILY_NOTIFICATIONS_BLUEPRINT

    app.register_blueprint(ECHO_BLUEPRINT, url_prefix="/echo")
    app.register_blueprint(PROSPECTING_BLUEPRINT, url_prefix="/prospect")
    app.register_blueprint(RESEARCH_BLUEPRINT, url_prefix="/research")
    app.register_blueprint(CLIENT_BLUEPRINT, url_prefix="/client")
    app.register_blueprint(
        MESSAGE_GENERATION_BLUEPRINT, url_prefix="/message_generation"
    )
    app.register_blueprint(ML_BLUEPRINT, url_prefix="/ml")
    app.register_blueprint(AUTOMATION_BLUEPRINT, url_prefix="/automation")
    app.register_blueprint(ANALYTICS_BLUEPRINT, url_prefix="/analytics")
    app.register_blueprint(EMAIL_GENERATION_BLUEPRINT, url_prefix="/email_generation")
    app.register_blueprint(CAMPAIGN_BLUEPRINT, url_prefix="/campaigns")
    app.register_blueprint(SIGHT_INBOX_BLUEPRINT, url_prefix="/sight_inbox")
    app.register_blueprint(EDITING_TOOLS_BLUEPRINT, url_prefix="/editing_tools")
    app.register_blueprint(RESPONSE_AI_BLUEPRINT, url_prefix="/response_ai")
    app.register_blueprint(ONBOARDING_BLUEPRINT, url_prefix="/onboarding")
    app.register_blueprint(ML_ADVERSARY_BLUEPRINT, url_prefix="/adversary")
    app.register_blueprint(EDITOR_BLUEPRINT, url_prefix="/editor")
    app.register_blueprint(LI_CONVERASTION_BLUEPRINT, url_prefix="/li_conversation")
    app.register_blueprint(DAILY_NOTIFICATIONS_BLUEPRINT, url_prefix="/daily_notifications")

    db.init_app(app)


@app.route("/")
def hello():
    return "SellScale API."


@app.route("/health-check")
def health_check():
    return "OK", 200


register_blueprints(app)

if __name__ == "__main__":
    app.run()
