from app import db


class Domain(db.Model):
    __tablename__ = "domain"

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False)
    forward_to = db.Column(db.String(255), nullable=False)

    aws = db.Column(db.Boolean, nullable=False)
    aws_hosted_zone_id = db.Column(db.String, nullable=True)

    dmarc_record = db.Column(db.String, nullable=True)
    dmarc_record_valid = db.Column(db.Boolean, nullable=True, default=False)
    spf_record = db.Column(db.String, nullable=True)
    spf_record_valid = db.Column(db.Boolean, nullable=True, default=False)
    dkim_record = db.Column(db.String, nullable=True)
    dkim_record_valid = db.Column(db.Boolean, nullable=True, default=False)
    forwarding_enabled = db.Column(db.Boolean, nullable=True, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "domain": self.domain,
            "forward_to": self.forward_to,
            "aws": self.aws,
            "aws_hosted_zone_id": self.aws_hosted_zone_id,
            "dmarc_record": self.dmarc_record,
            "dmarc_record_valid": self.dmarc_record_valid,
            "spf_record": self.spf_record,
            "spf_record_valid": self.spf_record_valid,
            "dkim_record": self.dkim_record,
            "dkim_record_valid": self.dkim_record_valid,
            "forwarding_enabled": self.forwarding_enabled,
        }
