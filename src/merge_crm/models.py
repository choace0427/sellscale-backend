from app import db


class ClientSyncCRM(db.Model):
    __tablename__ = "client_sync_crm"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    initiating_client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    account_token = db.Column(db.String, nullable=False)
    account_id = db.Column(db.String, nullable=False, default="")
    crm_type = db.Column(db.String, nullable=False)
    status_mapping = db.Column(db.JSON, nullable=False)
    event_handlers = db.Column(db.JSON, nullable=True)

    # Models syncing status
    lead_sync = db.Column(db.Boolean, nullable=True, default=False)
    contact_sync = db.Column(db.Boolean, nullable=True, default=False)
    account_sync = db.Column(db.Boolean, nullable=True, default=False)
    opportunity_sync = db.Column(db.Boolean, nullable=True, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "initiating_client_sdr_id": self.initiating_client_sdr_id,
            "account_token": self.account_token,
            "account_id": self.account_id,
            "crm_type": self.crm_type,
            "status_mapping": self.status_mapping,
            "event_handlers": self.event_handlers,
            "lead_sync": self.lead_sync,
            "contact_sync": self.contact_sync,
            "account_sync": self.account_sync,
            "opportunity_sync": self.opportunity_sync,
        }
class CRMContact(db.Model):
    __tablename__ = "crm_contact"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    company = db.Column(db.String, nullable=True)
    industry = db.Column(db.String, nullable=True)
    company_url = db.Column(db.String, nullable=True)
    do_not_contact = db.Column(db.Boolean, nullable=True, default=False)
    email_addresses = db.Column(db.ARRAY(db.String), nullable=True)
    crm_id = db.Column(db.String, nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company": self.company,
            "do_not_contact": self.do_not_contact,
            "crm_id": self.crm_id,
            "industry": self.industry,
            "company_url": self.company_url,
            "email_addresses": self.email_addresses,
            "client_id": self.client_id,
        }
