from app import db
import enum
from datetime import datetime, timedelta
import json

class SelixSessionStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    PENDING_OPERATOR = "PENDING_OPERATOR"
    BLOCKED = "BLOCKED"

    def all_statuses():
        return [
            SelixSessionStatus.ACTIVE,
            SelixSessionStatus.PENDING_OPERATOR,
            SelixSessionStatus.COMPLETE,
            SelixSessionStatus.CANCELLED,
            SelixSessionStatus.BLOCKED,
        ]


class SelixSessionTaskStatus(enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    IN_PROGRESS_REVIEW_NEEDED = "IN_PROGRESS_REVIEW_NEEDED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"

    def all_statuses():
        return [
            SelixSessionTaskStatus.QUEUED,
            SelixSessionTaskStatus.IN_PROGRESS,
            SelixSessionTaskStatus.IN_PROGRESS_REVIEW_NEEDED,
            SelixSessionTaskStatus.COMPLETE,
            SelixSessionTaskStatus.CANCELLED,
            SelixSessionTaskStatus.BLOCKED,
        ]


class SelixSession(db.Model):
    __tablename__ = "selix_session"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=False)
    session_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.Enum(SelixSessionStatus), nullable=False, default=SelixSessionStatus.ACTIVE)
    memory = db.Column(db.JSON, nullable=True)
    estimated_completion_time = db.Column(db.DateTime, nullable=True)
    actual_completion_time = db.Column(db.DateTime, nullable=True)
    assistant_id = db.Column(db.String(255), nullable=True)
    thread_id = db.Column(db.String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "session_name": self.session_name,
            "status": self.status.value,
            "memory": self.memory,
            "estimated_completion_time": self.estimated_completion_time,
            "actual_completion_time": self.actual_completion_time,
            "assistant_id": self.assistant_id,
            "thread_id": self.thread_id,
        }


class SelixSessionTask(db.Model):
    __tablename__ = "selix_session_task"

    id = db.Column(db.Integer, primary_key=True)
    selix_session_id = db.Column(db.Integer, db.ForeignKey("selix_session.id"), nullable=False)
    actual_completion_time = db.Column(db.DateTime, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String, nullable=False)
    status = db.Column(db.Enum(SelixSessionTaskStatus), nullable=False, default=SelixSessionTaskStatus.QUEUED)

    internal_notes = db.Column(db.String, nullable=True)

    order_number = db.Column(db.Integer, nullable=True)
    requires_review = db.Column(db.Boolean, nullable=True, default=False)

    proof_of_work_img = db.Column(db.String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "selix_session_id": self.selix_session_id,
            "actual_completion_time": self.actual_completion_time,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "proof_of_work_img": self.proof_of_work_img,
        }

class SelixActionCall(db.Model):
    __tablename__ = "selix_action_call"

    id = db.Column(db.Integer, primary_key=True)

    selix_session_id = db.Column(db.Integer, db.ForeignKey("selix_session.id"), nullable=False)
    action_title = db.Column(db.String(255), nullable=True)
    action_description = db.Column(db.String, nullable=True)

    action_function = db.Column(db.String(255), nullable=True)
    action_params = db.Column(db.JSON, nullable=True)

    actual_completion_time = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "created_time": self.created_at,
            "role": "system",
            "type": "action",
            "id": self.id,
            "selix_session_id": self.selix_session_id,
            "action_title": self.action_title,
            "action_description": self.action_description,
            "action_function": self.action_function,
            "action_params": self.action_params,
            "actual_completion_time": self.actual_completion_time,
        }