from app import db
from model_import import GeneratedMessageType


class AdversaryTrainingPoint(db.Model):
    __tablename__ = "adversary_training_point"

    id = db.Column(db.Integer, primary_key=True)

    generated_message_id = db.Column(db.Integer, db.ForeignKey("generated_message.id"), nullable=False)

    prompt = db.Column(db.String, nullable=False)
    completion = db.Column(db.String, nullable=False)

    mistake_description = db.Column(db.String, nullable=False)
    fix_instuctions = db.Column(db.String, nullable=False)

    use_in_training = db.Column(db.Boolean, nullable=False)
    used_in_past_training = db.Column(db.Boolean, nullable=False)


class AdversaryFineTuneHistory(db.Model):
    __tablename__ = "adversary_fine_tune_history"

    id = db.Column(db.Integer, primary_key=True)

    model_name = db.Column(db.String, nullable=False)
    new_training_points = db.Column(db.ARRAY(db.Integer), nullable=True)
    active = db.Column(db.Boolean, nullable=True)
    