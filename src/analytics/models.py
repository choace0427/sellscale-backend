from email.policy import default

from app import db


class SDRHealthStats(db.Model):
    __tablename__ = "sdr_health_stats"

    sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), primary_key=True)

    prospect_fit = db.Column(db.String)
    message_volume = db.Column(db.String)
    message_quality = db.Column(db.String)
    sdr_action_items = db.Column(db.String)
