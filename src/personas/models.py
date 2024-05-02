from app import db
import sqlalchemy as sa, enum

from src.contacts.models import SavedApolloQuery
from src.message_generation.models import StackRankedMessageGenerationConfiguration
from src.client.models import ClientSDR

class PersonaSplitRequestTaskStatus(enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NO_MATCH = "NO_MATCH"


class PersonaSplitRequest(db.Model):
    __tablename__ = "persona_split_request"

    id = db.Column(db.Integer, primary_key=True)
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))
    source_client_archetype_id = db.Column(
        db.Integer, db.ForeignKey("client_archetype.id")
    )
    destination_client_archetype_ids = db.Column(db.ARRAY(db.Integer))

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at,
            "client_sdr_id": self.client_sdr_id,
            "source_client_archetype_id": self.source_client_archetype_id,
            "destination_client_archetype_ids": self.destination_client_archetype_ids,
        }


class PersonaSplitRequestTask(db.Model):
    __tablename__ = "persona_split_request_task"

    id = db.Column(db.Integer, primary_key=True)
    persona_split_request_id = db.Column(
        db.Integer, db.ForeignKey("persona_split_request.id")
    )
    prospect_id = db.Column(db.Integer, db.ForeignKey("prospect.id"))
    destination_client_archetype_ids = db.Column(db.ARRAY(db.Integer), nullable=False)
    status = db.Column(sa.Enum(PersonaSplitRequestTaskStatus, create_constraint=False))
    tries = db.Column(db.Integer, default=0)
    prompt = db.Column(db.String)
    raw_completion = db.Column(db.String)
    json_completion = db.Column(db.JSON)


class Persona(db.Model):
    __tablename__ = "persona"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    client_sdr_id = db.Column(db.Integer, db.ForeignKey("client_sdr.id"))

    name = db.Column(db.String)
    description = db.Column(db.String)

    saved_apollo_query_id = db.Column(
        db.Integer, db.ForeignKey("saved_apollo_query.id")
    )
    stack_ranked_message_generation_configuration_id = db.Column(
        db.Integer, db.ForeignKey("stack_ranked_message_generation_configuration.id")
    )

    def to_dict(self, deep_get=True):
        payload = {
            "id": self.id,
            "client_id": self.client_id,
            "client_sdr_id": self.client_sdr_id,
            "name": self.name,
            "description": self.description,
            "saved_apollo_query_id": self.saved_apollo_query_id,
            "stack_ranked_message_generation_configuration_id": self.stack_ranked_message_generation_configuration_id,
        }
        if deep_get:
            asset_mappings = PersonaToAssetMapping.query.filter_by(
                persona_id=self.id
            ).all()
            payload["assets"] = [m.client_assets_id for m in asset_mappings]

            saved_apollo_query: SavedApolloQuery = SavedApolloQuery.query.get(
                self.saved_apollo_query_id
            )
            if saved_apollo_query:
                payload["saved_apollo_query"] = saved_apollo_query.to_dict()

            stack_ranked_message_generation_configuration = (
                StackRankedMessageGenerationConfiguration.query.get(
                    self.stack_ranked_message_generation_configuration_id
                )
            )
            if stack_ranked_message_generation_configuration:
                payload["stack_ranked_message_generation_configuration"] = (
                    stack_ranked_message_generation_configuration.to_dict()
                )

            client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            if client_sdr:
                payload["client_sdr"] = client_sdr.to_dict()

        return payload


class PersonaToAssetMapping(db.Model):
    __tablename__ = "persona_to_asset_mapping"

    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.Integer, db.ForeignKey("persona.id"), nullable=False)
    client_assets_id = db.Column(
        db.Integer, db.ForeignKey("client_assets.id"), nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "persona_id": self.persona_id,
            "client_assets_id": self.client_assets_id,
        }
