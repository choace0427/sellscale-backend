from typing import Optional
from app import db
from sqlalchemy.dialects.postgresql import JSONB


class SlackConnectedChannel(db.Model):  # type: ignore
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

    def to_dict(self, name_only: Optional[bool] = True):
        if name_only:
            return {
                "id": self.id,
                "client_id": self.client_id,
                "slack_channel_name": self.slack_channel_name,
                "slack_channel_name_normalized": self.slack_channel_name_normalized,
            }

        return {
            "id": self.id,
            "client_id": self.client_id,
            "slack_payload": self.slack_payload,
            "slack_channel_id": self.slack_channel_id,
            "slack_channel_name": self.slack_channel_name,
            "slack_channel_is_channel": self.slack_channel_is_channel,
            "slack_channel_is_group": self.slack_channel_is_group,
            "slack_channel_is_im": self.slack_channel_is_im,
            "slack_channel_created": self.slack_channel_created,
            "slack_channel_creator": self.slack_channel_creator,
            "slack_channel_is_archived": self.slack_channel_is_archived,
            "slack_channel_is_general": self.slack_channel_is_general,
            "slack_channel_unlinked": self.slack_channel_unlinked,
            "slack_channel_name_normalized": self.slack_channel_name_normalized,
            "slack_channel_is_shared": self.slack_channel_is_shared,
            "slack_channel_is_ext_shared": self.slack_channel_is_ext_shared,
            "slack_channel_is_org_shared": self.slack_channel_is_org_shared,
            "slack_channel_pending_shared": self.slack_channel_pending_shared,
            "slack_channel_is_pending_ext_shared": self.slack_channel_is_pending_ext_shared,
            "slack_channel_is_member": self.slack_channel_is_member,
            "slack_channel_is_private": self.slack_channel_is_private,
            "slack_channel_is_mpim": self.slack_channel_is_mpim,
            "slack_channel_topoic": self.slack_channel_topoic,
            "slack_channel_purpose": self.slack_channel_purpose,
        }
