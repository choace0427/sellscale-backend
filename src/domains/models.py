import enum
from app import db


class DomainSetupStatuses(enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    PURCHASE_DOMAIN = "PURCHASE_DOMAIN"
    SETUP_DNS_RECORDS = "SETUP_DNS_RECORDS"
    SETUP_FORWARDING = "SETUP_FORWARDING"
    SETUP_MAILBOXES = "SETUP_MAILBOXES"
    COMPLETED = "COMPLETED"


class DomainSetupTracker(db.Model):
    __tablename__ = "domain_setup_tracker"

    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), nullable=False)
    status = db.Column(
        db.Enum(DomainSetupStatuses),
        nullable=False,
        default=DomainSetupStatuses.NOT_STARTED,
    )

    # Core 3 stages for domain setup
    stage_purchase_domain = db.Column(db.Boolean, nullable=False, default=False)
    stage_setup_dns_records = db.Column(db.Boolean, nullable=False, default=False)
    stage_setup_forwarding = db.Column(db.Boolean, nullable=False, default=False)

    # Optional stage for mailbox setup
    setup_mailboxes = db.Column(db.Boolean, nullable=False, default=False)
    setup_mailboxes_usernames = db.Column(db.ARRAY(db.String), nullable=True)
    stage_setup_mailboxes = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "domain_id": self.domain_id,
            "status": self.status.value,
            "stage_purchase_domain": self.stage_purchase_domain,
            "stage_setup_dns_records": self.stage_setup_dns_records,
            "stage_setup_forwarding": self.stage_setup_forwarding,
            "setup_mailboxes": self.setup_mailboxes,
            "stage_setup_mailboxes": self.stage_setup_mailboxes,
        }


class Domain(db.Model):
    __tablename__ = "domain"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    domain = db.Column(db.String(255), nullable=False)
    forward_to = db.Column(db.String(255), nullable=False)

    aws = db.Column(db.Boolean, nullable=False)
    aws_domain_registration_status = db.Column(db.String, nullable=True)
    aws_domain_registration_job_id = db.Column(db.String, nullable=True)
    aws_hosted_zone_id = db.Column(db.String, nullable=True)
    aws_amplify_app_id = db.Column(db.String, nullable=True)
    aws_autorenew_enabled = db.Column(db.Boolean, nullable=True, default=False)

    dmarc_record = db.Column(db.String, nullable=True)
    dmarc_record_valid = db.Column(db.Boolean, nullable=True, default=False)
    spf_record = db.Column(db.String, nullable=True)
    spf_record_valid = db.Column(db.Boolean, nullable=True, default=False)
    dkim_record = db.Column(db.String, nullable=True)
    dkim_record_valid = db.Column(db.Boolean, nullable=True, default=False)
    forwarding_enabled = db.Column(db.Boolean, nullable=True, default=False)

    last_refreshed = db.Column(db.DateTime, nullable=True)
    domain_setup_tracker_id = db.Column(
        db.Integer, db.ForeignKey("domain_setup_tracker.id"), nullable=True
    )

    def to_dict(self):
        # Get the Setup details
        setup_tracker: DomainSetupTracker = DomainSetupTracker.query.filter_by(
            domain_id=self.id
        ).first()

        return {
            "id": self.id,
            "domain": self.domain,
            "forward_to": self.forward_to,
            "aws": self.aws,
            "aws_domain_registration_status": self.aws_domain_registration_status,
            "aws_domain_registration_job_id": self.aws_domain_registration_job_id,
            "aws_hosted_zone_id": self.aws_hosted_zone_id,
            "aws_amplify_app_id": self.aws_amplify_app_id,
            "aws_autorenew_enabled": self.aws_autorenew_enabled,
            "dmarc_record": self.dmarc_record,
            "dmarc_record_valid": self.dmarc_record_valid,
            "spf_record": self.spf_record,
            "spf_record_valid": self.spf_record_valid,
            "dkim_record": self.dkim_record,
            "dkim_record_valid": self.dkim_record_valid,
            "forwarding_enabled": self.forwarding_enabled,
            "last_refreshed": self.last_refreshed,
            "domain_setup_tracker": setup_tracker.to_dict() if setup_tracker else None,
        }
