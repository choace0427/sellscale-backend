from app import db


class ClientSyncCRM(db.Model):
    __tablename__ = "client_sync_crm"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))

    sync_type = db.Column(db.String, nullable=False)
    status_mapping = db.Column(db.JSON, nullable=False)
    event_handlers = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "sync_type": self.sync_type,
            "status_mapping": self.status_mapping,
            "event_handlers": self.event_handlers,
        }
