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
    citations = db.Column(db.ARRAY(db.String), nullable=True)

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
            "citations": self.citations,
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


# This class represents a Language Learning Model (LLM) entry in the database.
# It includes methods to convert the entry to a dictionary and call the LLM to get a response based on the stored system and user prompts.


# Example usage:
# Retrieve or create an LLM entry
# llm_entry = LLM(
#     name="example_llm",
#     system="You are a helpful assistant.",
#     user="What is the weather today?",
#     dependencies={"location": "New York"}
# )

# # Call the LLM to get a response
# response = llm_entry()
# print(response)


from enum import Enum

class LLMModel(Enum):
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4O = "gpt-4o"
    CLAUDE_OPUS = "claude-3-opus-20240229"
    CLAUDE_SONNET = "claude-3-5-sonnet-20240620"

class LLM(db.Model):
    __tablename__ = "llm"

    id = db.Column(db.Integer, primary_key=True)  # Unique identifier for each LLM entry
    name = db.Column(db.String, nullable=False, unique=True)  # Name key for the LLM entry
    system = db.Column(db.String, nullable=True)  # System attribute for the prompt, optional
    user = db.Column(db.String, nullable=False)  # User attribute for the prompt
    dependencies = db.Column(db.JSON, nullable=False, default={})  # Dependencies for the prompt
    model = db.Column(db.String, nullable=False, default=LLMModel.GPT_4O.value)  # Model to use for the LLM
    max_tokens = db.Column(db.Integer, nullable=False, default=100)  # Max tokens for the response

    def __init__(self, name, user=None, dependencies=None, system=None, model=None, max_tokens=None):
        existing_entry = LLM.query.filter_by(name=name).first()
        if existing_entry:
            if dependencies and existing_entry.dependencies.keys() == dependencies.keys():
                # Use the existing entry if dependencies match
                self.id = existing_entry.id
                self.name = existing_entry.name
                self.system = existing_entry.system if system is None else system
                self.user = existing_entry.user if user is None else user
                self.dependencies = existing_entry.dependencies
                self.model = existing_entry.model if model is None else model.value
                self.max_tokens = existing_entry.max_tokens if max_tokens is None else max_tokens

                # Ensure all parameters are set on the object
                system = self.system if system is None else system
                user = self.user if user is None else user
                dependencies = self.dependencies if dependencies is None else dependencies
                model = self.model if model is None else model.value
                max_tokens = self.max_tokens if max_tokens is None else max_tokens
            else:
                if dependencies and existing_entry.dependencies != dependencies:
                    print(f"Dependencies have changed for LLM entry with name '{name}'. Re-setting the object.")
                    existing_entry.name = name
                    existing_entry.system = system
                    existing_entry.user = user
                    existing_entry.dependencies = dependencies
                    existing_entry.model = model.value if model else existing_entry.model
                    existing_entry.max_tokens = max_tokens if max_tokens else existing_entry.max_tokens
                    db.session.commit()
                self.id = existing_entry.id
                self.name = existing_entry.name
                self.system = existing_entry.system
                self.user = existing_entry.user
                self.dependencies = existing_entry.dependencies
                self.model = existing_entry.model
                self.max_tokens = existing_entry.max_tokens
        else:
            self.name = name
            self.system = system
            self.user = user
            self.dependencies = dependencies or {}
            self.model = model.value if model else LLMModel.GPT_3_5_TURBO.value
            self.max_tokens = max_tokens if max_tokens else 100
            db.session.add(self)
            db.session.commit()
        
        if user and dependencies:
            # Inject dependencies into user and system strings if wrapped in {{}}
            for key, value in dependencies.items():
                placeholder = f"{{{{{key}}}}}"
                if self.user:
                    self.user = self.user.replace(placeholder, value)
                if self.system:
                    self.system = self.system.replace(placeholder, value)

            # Call the LLM to get a response based on the stored system and user prompts.
            from src.ml.services import wrapped_chat_gpt_completion

            messages = [{"role": "user", "content": self.user}]
            if self.system:
                messages.insert(0, {"role": "system", "content": self.system})

            self.response = wrapped_chat_gpt_completion(
                messages=messages,
                max_tokens=self.max_tokens,
                model=self.model,
            )
        else:
            self.response = None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "system": self.system,
            "user": self.user,
            "dependencies": self.dependencies,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "response": self.response,
        }

    def __call__(self):
        """
        Return the response from the LLM.
        
        Returns:
            str: The response from the LLM.
        """
        return self.response
