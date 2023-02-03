import hashlib
import json

from app import db
from model_import import ClientArchetype, GeneratedMessage, GNLPModel, Prospect
from src.email_outbound.models import (
    EmailInteractionState,
    EmailSchema,
    EmailSequenceState,
    ProspectEmail,
    ProspectEmailStatus,
    SalesEngagementInteractionRaw,
    SalesEngagementInteractionSource,
    SalesEngagementInteractionSS,
)


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


def create_sales_engagement_interaction_raw(
    client_id: int,
    client_archetype_id: int,
    client_sdr_id: int,
    payload: list,
    source: SalesEngagementInteractionSource,
) -> int:
    """Creates a SalesEngagementInteractionRaw entry using the JSON payload.
    We check the hash of the payload against payloads in the past. If the hash is the same, we return -1.
    Args:
        client_id (int): The client ID.
        client_archetype_id (int): The client archetype ID.
        client_sdr_id (int): The client SDR ID.
        payload (list): The JSON payload.
    Returns:
        int: The ID of the SalesEngagementInteractionRaw entry. -1 if the payload is a duplicate.
    """
    # Hash the payload so we can check against duplicates.
    json_dumps = json.dumps(payload)
    payload_hash_value: str = hashlib.sha256(json_dumps.encode()).hexdigest()
    # Check if we already have this payload in the database.
    exists = SalesEngagementInteractionRaw.query.filter_by(
        client_id=client_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        csv_data_hash=payload_hash_value,
    ).first()
    if exists:
        return -1
    # Create a SalesEngagementInteractionRaw entry using the payload as csv_data.
    raw_entry: SalesEngagementInteractionRaw = SalesEngagementInteractionRaw(
        client_id=client_id,
        client_archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        csv_data=payload,
        csv_data_hash=payload_hash_value,
        source=source.value,
    )
    db.session.add(raw_entry)
    db.session.commit()
    return raw_entry.id


def create_ss_prospect_dict(
    email: str,
    email_interaction_state: EmailInteractionState,
    email_sequence_state: EmailSequenceState,
) -> dict:
    """Helper to create a dictionary for a prospect, to be used in the SalesEngagementInteractionSS table.
    Should be called by functions which translate a raw csv into a SS csv.
    Args:
        email (str): email of the prospect
        email_interaction_state (EmailInteractionState.value): interaction state pulled from the csv
        email_sequence_state (EmailSequenceState.value): sequence state pulled from the csv
    Returns:
        dict: A dictionary with the keys "EMAIL", "EMAIL_INTERACTION_STATE", "EMAIL_SEQUENCE_STATE"
    """
    return {
        "EMAIL": email,
        "EMAIL_INTERACTION_STATE": email_interaction_state.value,
        "EMAIL_SEQUENCE_STATE": email_sequence_state.value,
    }
