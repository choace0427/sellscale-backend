from app import db
from model_import import GeneratedMessageType


class AdversaryTrainingPoint(db.Model):
    __tablename__ = "adversary_training_point"

    id = db.Column(db.Integer, primary_key=True)

    generated_message_id = db.Column(db.Integer, db.ForeignKey("generated_message.id"), nullable=False)
    generated_message_type = db.Column(db.Enum(GeneratedMessageType), nullable=False)

    prompt = db.Column(db.String, nullable=False)
    completion = db.Column(db.String, nullable=False)

    mistake_description = db.Column(db.String, nullable=False)
    fix_instuctions = db.Column(db.String, nullable=False)

    use_in_training = db.Column(db.Boolean, nullable=False)
