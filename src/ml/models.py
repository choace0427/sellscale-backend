from app import db
import enum


class ModelProvider(enum.Enum):
    OPENAI_GPT3 = "OPENAI_GPT3"


class GNLPModelType(enum.Enum):
    TRANSFORMER = "TRANSFORMER"
    OUTREACH = "OUTREACH"


class GNLPModel(db.Model):
    __tablename__ = "gnlp_models"

    id = db.Column(db.Integer, primary_key=True)

    model_provider = db.Column(db.Enum(ModelProvider), nullable=False)
    model_type = db.Column(db.Enum(GNLPModelType), nullable=False)
    model_description = db.Column(db.String, nullable=False)
    model_uuid = db.Column(db.String, nullable=False)
