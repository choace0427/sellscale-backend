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


class TextGeneration(db.Model):
    __tablename__ = "text_generation"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey('prospect.id'), nullable=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=True)

    prompt = db.Column(db.String, nullable=False)
    completion = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)

    human_edited = db.Column(db.Boolean, nullable=False, default=False)
    model_provider = db.Column(db.String, nullable=False)

    def to_dict(self):
      return {
        "prompt": self.prompt,
        "completion": self.completion,
        "status": self.status,
        "type": self.type,
        "human_edited": self.human_edited,
        "model_provider": self.model_provider,
        "prospect_id": self.prospect_id,
        "client_sdr_id": self.client_sdr_id,
      }


class AIResearcher(db.Model):
    __tablename__ = "ai_researcher"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    client_sdr_id_created_by = db.Column(
        db.Integer, db.ForeignKey("client_sdr.id"), nullable=False
    )


class AIResearcherQuestion(db.Model):
    __tablename__ = "ai_researcher_question"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False) # "QUESTION or "LINKEDIN"
    key = db.Column(db.String, nullable=False)
    relevancy = db.Column(db.String, nullable=False)
    researcher_id = db.Column(db.Integer, db.ForeignKey("ai_researcher.id"), nullable=False)