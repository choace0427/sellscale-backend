from app import db
from src.email_outbound.models import *
from model_import import ClientArchetype, GNLPModel, GeneratedMessage, Prospect


def create_email_schema(
    name: str,
    client_archetype_id: int,
):
    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        raise Exception("Client archetype not found")

    email_schema = EmailSchema(
        name=name,
        client_archetype_id=client_archetype_id,
    )
    db.session.add(email_schema)
    db.session.commit()
    return email_schema


def create_prospect_email(
    email_schema_id: int,
    prospect_id: int,
    personalized_first_line_id: int,
    batch_id: int,
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
        email_status=ProspectEmailStatus.DRAFT,
        batch_id=batch_id,
    )
    db.session.add(prospect_email)
    db.session.commit()
    return prospect_email


def batch_update_emails(
    payload: dict,
):
    for entry in payload:
        if "prospect_id" not in entry:
            return False, "Prospect ID missing in one of the rows"
        if "personalized_first_line" not in entry:
            return False, "Personalized first line missing in one of the rows"

    for entry in payload:
        prospect_id_payload: int = entry["prospect_id"]
        personalized_first_line_payload: str = entry["personalized_first_line"]

        prospect: Prospect = Prospect.query.get(prospect_id_payload)
        prospect_email_id: int = prospect.approved_prospect_email_id
        prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)

        if not prospect_email:
            continue

        personalized_first_line_id: int = prospect_email.personalized_first_line
        personalized_first_line: GeneratedMessage = GeneratedMessage.query.get(
            personalized_first_line_id
        )
        personalized_first_line.completion = personalized_first_line_payload

        db.session.add(personalized_first_line)
        db.session.commit()

    return True, "OK"
