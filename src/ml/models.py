from app import db
import enum


class ModelProvider(enum.Enum):
    OPENAI_GPT3 = "OPENAI_GPT3"


class GNLPModelType(enum.Enum):
    TRANSFORMER = "TRANSFORMER"  # data transformer
    OUTREACH = "OUTREACH"  # linkedin outbound
    EMAIL_FIRST_LINE = "EMAIL_FIRST_LINE"  # email outbound first line
    # todo(Aakash Adesara): Email Outreach
    # todo(Aakash Adesara): Text Outreach


class GNLPFinetuneJobStatuses(enum.Enum):
    INITIATED = "INITIATED"
    UPLOADED_JSONL_FILE = "BUILT_JSONL_FILE"
    STARTED_FINE_TUNE_JOB = "STARTED_FINE_TUNE_JOB"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class GNLPModel(db.Model):
    __tablename__ = "gnlp_models"

    id = db.Column(db.Integer, primary_key=True)

    model_provider = db.Column(db.Enum(ModelProvider), nullable=False)
    model_type = db.Column(db.Enum(GNLPModelType), nullable=False)
    model_description = db.Column(db.String, nullable=False)
    model_uuid = db.Column(db.String, nullable=False)

    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=True
    )


class GNLPModelFineTuneJobs(db.Model):
    __tablename__ = "gnlp_models_fine_tune_jobs"

    id = db.Column(db.Integer, primary_key=True)

    status = db.Column(db.Enum(GNLPFinetuneJobStatuses), nullable=False)
    archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id"), nullable=False
    )
    message_ids = db.Column(db.ARRAY(db.Integer), nullable=False)
    model_type = db.Column(db.Enum(GNLPModelType), nullable=False)

    jsonl_file_id = db.Column(db.String, nullable=True)
    jsonl_file_response = db.Column(db.JSON, nullable=True)

    finetune_job_id = db.Column(db.String, nullable=True)
    finetune_job_response = db.Column(db.JSON, nullable=True)

    gnlp_model_id = db.Column(
        db.Integer, db.ForeignKey("gnlp_models.id"), nullable=True
    )

    error = db.Column(db.String, nullable=True)


class ProfaneWords(db.Model):
    __tablename__ = "profane_words"

    id = db.Column(db.Integer, primary_key=True)
    words = db.Column(db.String, nullable=False)
