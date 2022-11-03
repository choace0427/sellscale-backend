from app import db
from src.email_outbound.models import *
from model_import import ClientArchetype, GNLPModel, GeneratedMessage, Prospect


def create_email_schema(
    name: str,
    client_archetype_id: int,
    personalized_first_line_gnlp_model_id: int,
):
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    gnlp_model: GNLPModel = GNLPModel.query.get(personalized_first_line_gnlp_model_id)
    if not ca:
        raise Exception("Client archetype not found")
    if not gnlp_model:
        raise Exception("GNLP model not found")

    email_schema = EmailSchema(
        name=name,
        client_archetype_id=client_archetype_id,
        personalized_first_line_gnlp_model_id=personalized_first_line_gnlp_model_id,
    )
    db.session.add(email_schema)
    db.session.commit()
    return email_schema


def create_prospect_email(
    email_schema_id: int,
    prospect_id: int,
    personalized_first_line_id: int,
):
    email_schema: EmailSchema = EmailSchema.query.get(email_schema_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    personalized_first_line: GeneratedMessage = GeneratedMessage.query.get(
        personalized_first_line_id
    )
    if not email_schema:
        raise Exception("Email schema not found")
    if not prospect:
        raise Exception("Prospect not found")
    if not personalized_first_line:
        raise Exception("Generated message not found")

    prospect_email = ProspectEmail(
        email_schema_id=email_schema_id,
        prospect_id=prospect_id,
        personalized_first_line=personalized_first_line_id,
    )
    db.session.add(prospect_email)
    db.session.commit()
    return prospect_email
