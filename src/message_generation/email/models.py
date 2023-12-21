from app import db
import enum


class EmailAutomatedReply(db.Model):
    __tablename__ = "email_automated_reply"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    prompt = db.Column(db.Text)
    email_body = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "client_sdr_id": self.client_sdr_id,
            "prompt": self.prompt,
            "email_body": self.email_body,
        }
