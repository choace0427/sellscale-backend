from email.policy import default
from app import db
from sqlalchemy.dialects.postgresql import JSONB


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

    message_to_dict = db.Column(JSONB, nullable=True)
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


class ActivityLog(db.Model):
    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    type = db.Column(db.String)
    name = db.Column(db.String)
    description = db.Column(db.String)

    def to_dict(self):
        from model_import import ClientSDR

        sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "sdr_name": sdr.name if sdr else "Unknown",
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
        }

class RetentionActivityLogs(db.Model):
    __tablename__ = "retention_activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    activity_tag = db.Column(db.String)

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_sdr_id": self.client_sdr_id,
            "activity_tag": self.activity_tag,
            "created_at": self.created_at,
        }