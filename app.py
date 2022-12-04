import os
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
