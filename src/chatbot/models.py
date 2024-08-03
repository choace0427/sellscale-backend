from app import db
import enum
from datetime import datetime, timedelta
import json

class SelixSessionStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    PENDING_OPERATOR = "PENDING_OPERATOR"

    def all_statuses():
        return [
            SelixSessionStatus.ACTIVE,
            SelixSessionStatus.PENDING_OPERATOR,
            SelixSessionStatus.COMPLETE,
            SelixSessionStatus.CANCELLED,
        ]


class SelixSessionTaskStatus(enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"

    def all_statuses():
        return [
            SelixSessionTaskStatus.QUEUED,
            SelixSessionTaskStatus.IN_PROGRESS,
            SelixSessionTaskStatus.COMPLETE,
            SelixSessionTaskStatus.CANCELLED,
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
