from email.policy import default

from app import db


class SDRHealthStats(db.Model):
    __tablename__ = "sdr_health_stats"

    sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), primary_key=True)

    prospect_fit = db.Column(db.String)
    message_volume = db.Column(db.String)
    message_quality = db.Column(db.String)
    sdr_action_items = db.Column(db.String)


class FeatureFlag(db.Model):
    __tablename__ = "feature_flag"

    feature = db.Column(db.String, primary_key=True)
    value = db.Column(db.Integer, default=0)


class AutoDeleteMessageAnalytics(db.Model):
    __tablename__ = "auto_delete_message_analytics"

    id = db.Column(db.Integer, primary_key=True)

    problem = db.Column(db.String)
    prospect = db.Column(db.String)
    sdr_name = db.Column(db.String)
    message = db.Column(db.String)
    send_date = db.Column(db.DateTime)
    channel = db.Column(db.String)


class ChatBotDataRepository(db.Model):
    __tablename__ = "chat_bot_data_repository"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    usage_analytics_data = db.Column(db.JSON, nullable=True)
    tam_graph_data = db.Column(db.JSON, nullable=True)
    rejection_report_data = db.Column(db.JSON, nullable=True)
    demo_feedback_data = db.Column(db.JSON, nullable=True)
    message_analytics_data = db.Column(db.JSON, nullable=True)
