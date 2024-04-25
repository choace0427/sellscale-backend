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
