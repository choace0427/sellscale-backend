from app import db
import enum
class QuestionEnrichmentRequest(db.Model):
    __tablename__ = "question_enrichment_request"

    id = db.Column(db.Integer, primary_key=True)
    
    prospect_ids = db.Column(db.ARRAY(db.Integer), nullable=False)
    question = db.Column(db.String, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "prospect_ids": self.prospect_ids,
            "question": self.question
        }


class QuestionEnrichmentRowStatus(enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
class QuestionEnrichmentRow(db.Model):
    __tablename__ = "question_enrichment_row"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, nullable=False)

    question = db.Column(db.String, nullable=False)
    output = db.Column(db.Boolean, nullable=True)

    status = db.Column(db.Enum(QuestionEnrichmentRowStatus), nullable=False)

    retries = db.Column(db.Integer, nullable=False)
    error = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "question": self.question,
            "output": self.output,
            "retries": self.retries,
            "error": self.error
        }