from app import db
from enum import Enum
from sqlalchemy.dialects.postgresql import JSONB


class SlackAuthentication(db.Model):  # type: ignore
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
