import enum
from app import db


class HunterVerifyStatus(enum.Enum):
    COMPLETE = "COMPLETE"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
    FAILED = "FAILED"


class EmailStore(db.Model):
    """EmailStore will be the central database for all email addresses that we possess on prospects (past, current, and future).

    EmailStore keeps track of the validity of emails, and the source of the email.
    """
    __tablename__ = "email_store"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String, nullable=False, index=True, unique=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    company_name = db.Column(db.String, nullable=True)

    # Comes from Hunter (https://hunter.io/api-documentation#email-verifier) --->
    hunter_status = db.Column(db.String, nullable=True)
    hunter_score = db.Column(db.Integer, nullable=True)
    hunter_regexp = db.Column(db.Boolean, nullable=True)
    hunter_gibberish = db.Column(db.Boolean, nullable=True)
    hunter_disposable = db.Column(db.Boolean, nullable=True)
    hunter_webmail = db.Column(db.Boolean, nullable=True)
    hunter_mx_records = db.Column(db.Boolean, nullable=True)
    hunter_smtp_server = db.Column(db.Boolean, nullable=True)
    hunter_smtp_check = db.Column(db.Boolean, nullable=True)
    hunter_accept_all = db.Column(db.Boolean, nullable=True)
    hunter_block = db.Column(db.Boolean, nullable=True)
    hunter_sources = db.Column(db.ARRAY(db.JSON), nullable=True)
    verification_status_hunter = db.Column(db.Enum(HunterVerifyStatus), nullable=True)
    verification_status_hunter_attempts = db.Column(db.Integer, nullable=True)
    verification_status_hunter_error = db.Column(db.JSON, nullable=True)
    # <--- Comes from Hunter

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company_name": self.company_name,
            "hunter_status": self.hunter_status,
            "hunter_score": self.hunter_score,
            "hunter_regexp": self.hunter_regexp,
            "hunter_gibberish": self.hunter_gibberish,
            "hunter_disposable": self.hunter_disposable,
            "hunter_webmail": self.hunter_webmail,
            "hunter_mx_records": self.hunter_mx_records,
            "hunter_smtp_server": self.hunter_smtp_server,
            "hunter_smtp_check": self.hunter_smtp_check,
            "hunter_accept_all": self.hunter_accept_all,
            "hunter_block": self.hunter_block,
            "hunter_sources": self.hunter_sources,
            "verification_status_hunter": self.verification_status_hunter,
            "verification_status_hunter_attempts": self.verification_status_hunter_attempts,
            "verification_status_hunter_error": self.verification_status_hunter_error,
        }

