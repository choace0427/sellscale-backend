from app import db
from enum import Enum
from sqlalchemy.dialects.postgresql import JSONB


class SlackAuthentication(db.Model):
    __tablename__ = "slack_authentication"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)

    # Slack IDs and Tokens
    slack_payload = db.Column(JSONB, nullable=False)
    slack_access_token = db.Column(db.String(255), nullable=False)
    slack_token_type = db.Column(db.String(255), nullable=False)
    slack_scope = db.Column(db.String, nullable=False)
    slack_bot_user_id = db.Column(db.String(255), nullable=False)
    slack_app_id = db.Column(db.String(255), nullable=False)
    slack_team_name = db.Column(db.String, nullable=True)
    slack_team_id = db.Column(db.String(255), nullable=True)
    slack_enterprise_name = db.Column(db.String, nullable=True)
    slack_enterprise_id = db.Column(db.String(255), nullable=True)
    slack_authed_user_id = db.Column(db.String(255), nullable=True)
    slack_authed_user_scope = db.Column(db.String, nullable=True)
    slack_authed_user_access_token = db.Column(db.String(255), nullable=True)
    slack_authed_user_token_type = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_sdr_id": self.client_sdr_id,
            "slack_payload": self.slack_payload,
            "slack_access_token": self.slack_access_token,
            "slack_token_type": self.slack_token_type,
            "slack_scope": self.slack_scope,
            "slack_bot_user_id": self.slack_bot_user_id,
            "slack_app_id": self.slack_app_id,
            "slack_team_name": self.slack_team_name,
            "slack_team_id": self.slack_team_id,
            "slack_enterprise_name": self.slack_enterprise_name,
            "slack_enterprise_id": self.slack_enterprise_id,
            "slack_authed_user_id": self.slack_authed_user_id,
            "slack_authed_user_scope": self.slack_authed_user_scope,
            "slack_authed_user_access_token": self.slack_authed_user_access_token,
            "slack_authed_user_token_type": self.slack_authed_user_token_type,
        }
