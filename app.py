import os
import sys

from kombu import Queue, Exchange
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy

from flask_cors import CORS
from flask_migrate import Migrate

from flask_sqlalchemy import SQLAlchemy
from app_slack import SlackAppHandlerPair
from src.setup.TimestampedModel import TimestampedModel
from src.utils.scheduler import *
from src.utils.slack import URL_MAP
import boto3
from src.utils.access import is_production

from celery import Celery
from src.utils.slack import send_slack_message

if is_production():
    import sentry_sdk
    from sentry_sdk.integrations.tornado import TornadoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn="https://e8251e81ed8847a69607f976b423e17c@o4504749544767488.ingest.sentry.io/4504749545619456",
        integrations=[
            FlaskIntegration(),
            CeleryIntegration(),
            TornadoIntegration(),
            RedisIntegration(),
            SqlalchemyIntegration(),
        ],
        auto_enabling_integrations=False,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,
    )

    def sentry_excepthook(exc_type, exc_value, exc_traceback):
        with sentry_sdk.push_scope() as scope:
            # You can add additional context or tags here if needed
            scope.set_tag("exception_type", exc_type)
            scope.set_extra("traceback", exc_traceback)

        # Capture the exception with Sentry
        sentry_sdk.capture_exception(exc_value)

    # Set the custom excepthook function as the default excepthook
    sys.excepthook = sentry_excepthook


slack_app, slack_app_handler = SlackAppHandlerPair()


def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=app.config["CELERY_BROKER_URL"],
    )
    celery.conf.update(app.config)

    celery.conf.broker_transport_options = {
        "queue_order_strategy": "priority",
    }

    # These configs will be applied across all Celery instances

    default_exchange = Exchange("default", type="direct")
    # prospecting_exchange = Exchange("prospecting", type="direct")
    # message_generation_exchange = Exchange("message_generation", type="direct")
    # email_scheduler = Exchange("email_scheduler", type="direct")
    celery.conf.task_queues = (
        Queue("default", default_exchange, routing_key="default"),
    )
    #     Queue("prospecting", prospecting_exchange, routing_key="prospecting"),
    #     Queue(
    #         "message_generation",
    #         message_generation_exchange,
    #         routing_key="message_generation",
    #     ),
    #     Queue(
    #         "email_scheduler",
    #         email_scheduler,
    #         routing_key="email_scheduler",
    #     ),
    # )
    celery.conf.task_default_queue = "default"
    celery.conf.task_default_exchange = "default"
    celery.conf.task_default_routing_key = "default"
    celery.conf.task_default_priority = 5  # 0 is the highest
    celery.conf.task_annotations = {
        f"src.message_generation.services.research_and_generate_outreaches_for_prospect": {
            "rate_limit": "2/s",
        },
        f"src.message_generation.services.generate_prospect_email": {
            "rate_limit": "2/s",
        },
        f"src.ml.services.icp_classify": {
            "rate_limit": "2/s",
        },
        f"app.add_together": {
            "rate_limit": "1/s",
        },
        f"src.ml.services.test_rate_limiter": {
            "rate_limit": "2/s",
        },
        f"src.email_outbound.email_store.services.email_store_hunter_verify": {
            "rate_limit": "2/s",
        },
        f"src.smartlead.services.upload_prospect_to_campaign": {
            "rate_limit": "1/s",
        },
    }

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


# Test

app = Flask(__name__)

app.config["SECRET_KEY"] = "secret!!"

app.config.update(
    CELERY_BROKER_URL=os.environ.get("CELERY_REDIS_URL"),
)
celery = make_celery(app)
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"

app.config.from_object(os.environ["APP_SETTINGS"])
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Updated on August 11, 2023, previous values were default. (pool size 5, overflow 10)
# app.config['SQLALCHEMY_POOL_SIZE'] = 20
# app.config['SQLALCHEMY_MAX_OVERFLOW'] = 40
sqlalchemy_engine_options = {"max_overflow": 40, "pool_size": 20, "pool_pre_ping": True}
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = sqlalchemy_engine_options

# Initialize AWS clients
aws_route53domains_client = boto3.client(
    "route53domains",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_ACCESS_KEY_SECRET"),
    region_name="us-east-1",
)
aws_route53_client = boto3.client(
    "route53",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_ACCESS_KEY_SECRET"),
    region_name="us-east-1",
)
aws_ses_client = boto3.client(
    "ses",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_ACCESS_KEY_SECRET"),
    region_name="us-east-1",
)
aws_sesv2_client = boto3.client(
    "sesv2",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_ACCESS_KEY_SECRET"),
    region_name="us-east-1",
)
aws_workmail_client = boto3.client(
    "workmail",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_ACCESS_KEY_SECRET"),
    region_name="us-east-1",
)
aws_amplify_client = boto3.client(
    "amplify",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_ACCESS_KEY_SECRET"),
    region_name="us-east-1",
)

db: SQLAlchemy = SQLAlchemy(model_class=TimestampedModel)
migrate = Migrate(app, db)

# chroma_client = chromadb.HttpClient(host='https://vector-db-zakq.onrender.com', port=8000)

from model_import import *


@celery.task()
def add_together(a, b):
    from datetime import datetime

    send_slack_message(
        message="Testing from slack! Time:" + str(datetime.utcnow()),
        webhook_urls=[URL_MAP["eng-sandbox"]],
    )
    return a + b


def register_blueprints(app):
    from src.client.sdr.controllers import CLIENT_SDR_BLUEPRINT
    from src.webhooks.controllers import WEBHOOKS_BLUEPRINT
    from src.echo.controllers import ECHO_BLUEPRINT
    from src.prospecting.controllers import PROSPECTING_BLUEPRINT
    from src.research.controllers import RESEARCH_BLUEPRINT
    from src.client.controllers import CLIENT_BLUEPRINT
    from src.message_generation.controllers import MESSAGE_GENERATION_BLUEPRINT
    from src.ml.controllers import ML_BLUEPRINT
    from src.automation.controllers import AUTOMATION_BLUEPRINT
    from src.authentication.controllers import AUTHENTICATION_BLUEPRINT
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
    from src.integrations.controllers import INTEGRATION_BLUEPRINT
    from src.voyager.controllers import VOYAGER_BLUEPRINT
    from src.bump_framework.controllers import BUMP_FRAMEWORK_BLUEPRINT
    from src.email_sequencing.controllers import EMAIL_SEQUENCING_BLUEPRINT
    from src.personas.controllers import PERSONAS_BLUEPRINT
    from src.voice_builder.controllers import VOICE_BUILDER_BLUEPRINT
    from src.company.controllers import COMPANY_BLUEPRINT
    from src.calendly.controllers import CALENDLY_BLUEPRINT
    from src.simulation.controllers import SIMULATION_BLUEPRINT
    from src.automation.phantom_buster.controllers import PHANTOM_BUSTER_BLUEPRINT
    from src.individual.controllers import INDIVIDUAL_BLUEPRINT
    from src.prospecting.icp_score.controllers import ICP_SCORING_BLUEPRINT
    from src.message_generation.email.controllers import (
        MESSAGE_GENERATION_EMAIL_BLUEPRINT,
    )
    from src.client.archetype.controllers import CLIENT_ARCHETYPE_BLUEPRINT
    from src.client.sdr.email.controllers import SDR_EMAIL_BLUEPRINT
    from src.email_scheduling.controllers import EMAIL_SCHEDULING_BLUEPRINT
    from src.warmup_snapshot.controllers import WARMUP_SNAPSHOT
    from src.prospecting.question_enrichment.controllers import (
        QUESTION_ENRICHMENT_BLUEPRINT,
    )
    from src.li_conversation.controllers_linkedin_template import (
        LINKEDIN_TEMPLATE_BLUEPRINT,
    )
    from src.smartlead.controllers import SMARTLEAD_BLUEPRINT
    from src.smartlead.webhooks.controllers import SMARTLEAD_WEBHOOKS_BLUEPRINT
    from src.triggers.controllers import TRIGGERS_BLUEPRINT
    from src.weekly_report.controllers import WEEKLY_REPORT_BLUEPRINT
    from src.sockets.controllers import SOCKETS_BLUEPRINT
    from src.domains.controllers import DOMAINS_BLUEPRINT

    from src.usage.controllers import USAGE_BLUEPRINT
    from src.ai_requests.controllers import AI_REQUESTS
    from src.notifications.controllers import NOTIFICATION_BLUEPRINT
    from src.segment.controllers import SEGMENT_BLUEPRINT
    from src.email_replies.controllers import EMAIL_REPLIES_BLUEPRINT
    from src.contacts.controllers import CONTACTS_BLUEPRINT
    from src.operator_dashboard.controllers import OPERATOR_DASHBOARD_BLUEPRINT

    from src.subscriptions.controllers import SUBSCRIPTIONS_BLUEPRINT
    from src.slack.controllers import SLACK_BLUEPRINT
    from src.slack.auth.controllers import SLACK_AUTH_BLUEPRINT
    from src.track.controllers import TRACK_BLUEPRINT
    from src.merge_crm.controllers import MERGE_CRM_BLUEPRINT

    from src.slack.events.controllers import SLACK_EVENTS_BLUEPRINT
    from src.link_urls.controllers import LINK_URL_BLUEPRINT
    from src.outbound_quota.controllers import OUTBOUND_QUOTA_BLUEPRINT

    from src.utilization.controllers import UTILIZATION_BLUEPRINT
    from src.prospecting.upload.controllers import PROSPECTING_UPLOAD_BLUEPRINT
    from src.merge_crm.webhooks.controllers import MERGE_CRM_WEBHOOKS_BLUEPRINT

    from src.apollo.controllers import APOLLO_REQUESTS
    from src.strategies.controllers import STRATEGIES_BLUEPRINT

    app.register_blueprint(CLIENT_ARCHETYPE_BLUEPRINT, url_prefix="/client/archetype")
    app.register_blueprint(WEBHOOKS_BLUEPRINT, url_prefix="/webhooks")
    app.register_blueprint(ECHO_BLUEPRINT, url_prefix="/echo")
    app.register_blueprint(PROSPECTING_BLUEPRINT, url_prefix="/prospect")
    app.register_blueprint(RESEARCH_BLUEPRINT, url_prefix="/research")
    app.register_blueprint(CLIENT_BLUEPRINT, url_prefix="/client")
    app.register_blueprint(CLIENT_SDR_BLUEPRINT, url_prefix="/client/sdr")
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
    app.register_blueprint(
        DAILY_NOTIFICATIONS_BLUEPRINT, url_prefix="/daily_notifications"
    )
    app.register_blueprint(AUTHENTICATION_BLUEPRINT, url_prefix="/auth")
    app.register_blueprint(INTEGRATION_BLUEPRINT, url_prefix="/integration")
    app.register_blueprint(VOYAGER_BLUEPRINT, url_prefix="/voyager")
    app.register_blueprint(BUMP_FRAMEWORK_BLUEPRINT, url_prefix="/bump_framework")
    app.register_blueprint(EMAIL_SEQUENCING_BLUEPRINT, url_prefix="/email_sequence")
    app.register_blueprint(PERSONAS_BLUEPRINT, url_prefix="/personas")
    app.register_blueprint(VOICE_BUILDER_BLUEPRINT, url_prefix="/voice_builder")
    app.register_blueprint(COMPANY_BLUEPRINT, url_prefix="/company")
    app.register_blueprint(CALENDLY_BLUEPRINT, url_prefix="/calendly")
    app.register_blueprint(SIMULATION_BLUEPRINT, url_prefix="/simulation")
    app.register_blueprint(
        PHANTOM_BUSTER_BLUEPRINT, url_prefix="/automation/phantom_buster"
    )
    app.register_blueprint(
        MESSAGE_GENERATION_EMAIL_BLUEPRINT, url_prefix="/message_generation/email"
    )
    app.register_blueprint(INDIVIDUAL_BLUEPRINT, url_prefix="/individual")
    app.register_blueprint(ICP_SCORING_BLUEPRINT, url_prefix="/icp_scoring")
    app.register_blueprint(SDR_EMAIL_BLUEPRINT, url_prefix="/client/sdr/email")
    app.register_blueprint(EMAIL_SCHEDULING_BLUEPRINT, url_prefix="/email/schedule")
    app.register_blueprint(WARMUP_SNAPSHOT, url_prefix="/warmup")
    app.register_blueprint(
        QUESTION_ENRICHMENT_BLUEPRINT, url_prefix="/question_enrichment"
    )
    app.register_blueprint(LINKEDIN_TEMPLATE_BLUEPRINT, url_prefix="/linkedin_template")
    app.register_blueprint(SMARTLEAD_BLUEPRINT, url_prefix="/smartlead")
    app.register_blueprint(
        SMARTLEAD_WEBHOOKS_BLUEPRINT, url_prefix="/smartlead/webhooks"
    )
    app.register_blueprint(TRIGGERS_BLUEPRINT, url_prefix="/triggers")
    app.register_blueprint(WEEKLY_REPORT_BLUEPRINT, url_prefix="/weekly_report")
    app.register_blueprint(SOCKETS_BLUEPRINT, url_prefix="/sockets")
    app.register_blueprint(DOMAINS_BLUEPRINT, url_prefix="/domains")
    app.register_blueprint(USAGE_BLUEPRINT, url_prefix="/usage")
    app.register_blueprint(AI_REQUESTS, url_prefix="/ai_requests")
    app.register_blueprint(NOTIFICATION_BLUEPRINT, url_prefix="/notification")
    app.register_blueprint(SEGMENT_BLUEPRINT, url_prefix="/segment")
    app.register_blueprint(EMAIL_REPLIES_BLUEPRINT, url_prefix="/email/replies")
    app.register_blueprint(CONTACTS_BLUEPRINT, url_prefix="/contacts")
    app.register_blueprint(
        OPERATOR_DASHBOARD_BLUEPRINT, url_prefix="/operator_dashboard"
    )
    app.register_blueprint(SUBSCRIPTIONS_BLUEPRINT, url_prefix="/subscriptions")
    app.register_blueprint(SLACK_BLUEPRINT, url_prefix="/slack")
    app.register_blueprint(SLACK_AUTH_BLUEPRINT, url_prefix="/slack/authentication")
    app.register_blueprint(TRACK_BLUEPRINT, url_prefix="/track")
    app.register_blueprint(MERGE_CRM_BLUEPRINT, url_prefix="/merge_crm")
    app.register_blueprint(
        MERGE_CRM_WEBHOOKS_BLUEPRINT, url_prefix="/merge/crm/webhooks"
    )
    app.register_blueprint(SLACK_EVENTS_BLUEPRINT, url_prefix="/slack/events")
    app.register_blueprint(LINK_URL_BLUEPRINT, url_prefix="/link_url")
    app.register_blueprint(OUTBOUND_QUOTA_BLUEPRINT, url_prefix="/outbound_quota")

    app.register_blueprint(UTILIZATION_BLUEPRINT, url_prefix="/utilizationv2")
    app.register_blueprint(PROSPECTING_UPLOAD_BLUEPRINT, url_prefix="/prospect/upload")

    app.register_blueprint(APOLLO_REQUESTS, url_prefix="/apollo")
    app.register_blueprint(STRATEGIES_BLUEPRINT, url_prefix="/strategies")

    db.init_app(app)


@app.route("/")
def hello():
    return "SellScale API."


@app.route("/health-check")
def health_check():
    return "OK", 200


register_blueprints(app)


if __name__ == "__main__":
    pass
    # socketio.run(app, debug=True)
