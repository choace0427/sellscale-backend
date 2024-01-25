from app import db
from sqlalchemy.dialects.postgresql import JSONB


class SlackConnectedChannel(db.Model):
    __tablename__ = "slack_connected_channel"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)

    # Slack Channel
    slack_payload = db.Column(JSONB, nullable=False)
    slack_channel_id = db.Column(db.String(255), nullable=False)
    slack_channel_name = db.Column(db.String(255), nullable=False)
    slack_channel_is_channel = db.Column(db.Boolean, nullable=False)
    slack_channel_is_group = db.Column(db.Boolean, nullable=False)
    slack_channel_is_im = db.Column(db.Boolean, nullable=False)
    slack_channel_created = db.Column(db.Integer, nullable=False)
    slack_channel_creator = db.Column(db.String(255), nullable=False)
    slack_channel_is_archived = db.Column(db.Boolean, nullable=False)
    slack_channel_is_general = db.Column(db.Boolean, nullable=False)
    slack_channel_unlinked = db.Column(db.Integer, nullable=False)
    slack_channel_name_normalized = db.Column(db.String(255), nullable=False)
    slack_channel_is_shared = db.Column(db.Boolean, nullable=False)
    slack_channel_is_ext_shared = db.Column(db.Boolean, nullable=False)
    slack_channel_is_org_shared = db.Column(db.Boolean, nullable=False)
    slack_channel_pending_shared = db.Column(db.ARRAY(JSONB), nullable=True)
    slack_channel_is_pending_ext_shared = db.Column(db.Boolean, nullable=False)
    slack_channel_is_member = db.Column(db.Boolean, nullable=False)
    slack_channel_is_private = db.Column(db.Boolean, nullable=False)
    slack_channel_is_mpim = db.Column(db.Boolean, nullable=False)
    slack_channel_topoic = db.Column(JSONB, nullable=True)
    slack_channel_purpose = db.Column(JSONB, nullable=True)
