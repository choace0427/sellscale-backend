from app import db

import enum

from src.email_outbound.models import ProspectEmail
from src.email_sequencing.models import EmailSequenceStep, EmailSubjectLineTemplate
from src.prospecting.models import Prospect


class EmailMessagingStatus(enum.Enum):
    NEEDS_GENERATION = "NEEDS_GENERATION"
    SCHEDULED = "SCHEDULED"
    SENT = "SENT"
    FAILED = "FAILED"


class EmailMessagingType(enum.Enum):
    INITIAL_EMAIL = "INITIAL_EMAIL"
    FOLLOW_UP_EMAIL = "FOLLOW_UP_EMAIL"


class EmailMessagingSchedule(db.Model):
    __tablename__ = "email_messaging_schedule"

    id = db.Column(db.Integer, primary_key=True)

    # Identification Foreign Keys
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=False)
    prospect_email_id = db.Column(db.Integer, db.ForeignKey("prospect_email.id"), nullable=False)

    # Type of email
    email_type = db.Column(db.Enum(EmailMessagingType), nullable=False)

    # Generated Message and Template Foreign Keys
    subject_line_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id"), nullable=True)
    body_id = db.Column(
        db.Integer, db.ForeignKey("generated_message.id"), nullable=True)
    email_subject_line_template_id = db.Column(
        db.Integer, db.ForeignKey("email_subject_line_template.id"), nullable=True)
    email_body_template_id = db.Column(
        db.Integer, db.ForeignKey("email_sequence_step.id"), nullable=False)

    # Send Status
    send_status = db.Column(db.Enum(EmailMessagingStatus), nullable=False)
    send_status_error = db.Column(db.String, nullable=True)

    # Scheduled Date
    date_scheduled = db.Column(db.DateTime, nullable=False)

    # Nylas Data
    nylas_message_id = db.Column(db.String, nullable=True)
    nylas_thread_id = db.Column(db.String, nullable=True)

    def to_dict(self):
        # Get the Prospect
        prospect_email: ProspectEmail = ProspectEmail.query.filter_by(id=self.prospect_email_id).first()
        prospect: Prospect = Prospect.query.filter_by(id=prospect_email.prospect_id).first()

        # Get the templates
        subject_line_template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.filter_by(id=self.email_subject_line_template_id).first()
        body_template: EmailSequenceStep = EmailSequenceStep.query.filter_by(id=self.email_body_template_id).first()

        return {
            "id": self.id,
            "client_sdr_id": self.client_sdr_id,
            "email_type": self.email_type.value,
            "subject_line_id": self.subject_line_id,
            "body_id": self.body_id,
            "send_status": self.send_status.value,
            "send_status_error": self.send_status_error,
            "date_scheduled": self.date_scheduled,
            "nylas_message_id": self.nylas_message_id,
            "nylas_thread_id": self.nylas_thread_id,
            "subject_line_template": subject_line_template.to_dict() if subject_line_template else None,
            "body_template": body_template.to_dict() if body_template else None,
            "prospect_email": prospect_email.to_dict() if prospect_email else None,
            "prospect": prospect.to_dict() if prospect else None
        }

