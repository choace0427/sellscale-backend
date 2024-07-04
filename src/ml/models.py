from app import db
import enum


class ProfaneWords(db.Model):
    __tablename__ = "profane_words"

    id = db.Column(db.Integer, primary_key=True)
    words = db.Column(db.String, nullable=False)


class TextGeneration(db.Model):
    __tablename__ = "text_generation"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=True)
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

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "client_id": self.client_id,
            "client_sdr_id_created_by": self.client_sdr_id_created_by,
        }


class AIResearcherQuestion(db.Model):
    __tablename__ = "ai_researcher_question"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False)  # "QUESTION or "LINKEDIN"
    key = db.Column(db.String, nullable=False)
    relevancy = db.Column(db.String, nullable=False)
    researcher_id = db.Column(
        db.Integer, db.ForeignKey("ai_researcher.id"), nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "key": self.key,
            "relevancy": self.relevancy,
            "researcher_id": self.researcher_id,
        }


class AIResearcherAnswer(db.Model):
    __tablename__ = "ai_researcher_answer"

    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"), nullable=True)
    question_id = db.Column(
        db.Integer, db.ForeignKey("ai_researcher_question.id"), nullable=False
    )
    is_yes_response = db.Column(db.Boolean, nullable=False)
    short_summary = db.Column(db.String, nullable=False)
    raw_response = db.Column(db.String, nullable=False)
    relevancy_explanation = db.Column(db.String, nullable=True)

    def to_dict(self, deep_get: bool = False):
        question: AIResearcherQuestion = AIResearcherQuestion.query.get(
            self.question_id
        )

        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "question_id": self.question_id,
            "is_yes_response": self.is_yes_response,
            "short_summary": self.short_summary,
            "raw_response": self.raw_response,
            "question": question.to_dict() if deep_get else None,
            "relevancy_explanation": self.relevancy_explanation,
        }

class FewShot(db.Model):
    __tablename__ = "few_shot"

    id = db.Column(db.Integer, primary_key=True)  # Unique identifier for each FewShot entry
    original_string = db.Column(db.String, nullable=False)  # The original string before any edits
    edited_string = db.Column(db.String, nullable=False)  # The string after edits have been made
    nuance = db.Column(db.String, nullable=False)  # Additional nuance or context for the edited string
    ai_voice_id = db.Column(db.Integer, db.ForeignKey("ai_voice.id"), nullable=False)  # Foreign key linking to the AI Voice

    def to_dict(self):
        return {
            "id": self.id,
            "nuance": self.nuance,
            "edited_string": self.edited_string,
            "original_string": self.original_string,
        }

class AIVoice(db.Model):
    __tablename__ = "ai_voice"

    id = db.Column(db.Integer, primary_key=True)  # Unique identifier for each AIVoice entry
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)  # Foreign key linking to the client
    client_sdr_created_by = db.Column(db.Integer, db.ForeignKey("client_sdr.id"), nullable=False)  # Foreign key linking to the client SDR who created this entry
    name = db.Column(db.String, nullable=False)  # The name of the AI Voice

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "client_sdr_created_by": self.client_sdr_created_by,
            "name": self.name,
        }
