from app import db

class SightOnboarding(db.Model):
    __tablename__ = "sight_onboarding"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=False)

    is_onboarding_complete = db.Column(db.Boolean, nullable=True, default=False)

    completed_credentials = db.Column(db.Boolean, nullable=True, default=False)
    completed_first_persona = db.Column(db.Boolean, nullable=True, default=False)
    completed_ai_behavior = db.Column(db.Boolean, nullable=True, default=False)
    completed_first_campaign = db.Column(db.Boolean, nullable=True, default=False)
    completed_go_live = db.Column(db.Boolean, nullable=True, default=False)
