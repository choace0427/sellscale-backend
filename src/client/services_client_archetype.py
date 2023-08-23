from sqlalchemy import update
from app import db
from model_import import ResearchPointType, ClientArchetype
from typing import Union, Optional
from src.client.models import ClientSDR
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.ml.services import mark_queued_and_classify
from src.prospecting.models import Prospect, ProspectStatus

from src.utils.slack import URL_MAP, send_slack_message


def update_transformer_blocklist(client_archetype_id: int, new_blocklist: list) -> any:
    """
    Set's the client archetype'ss transformer blocker

    Args:
        client_archetype_id (int): Client Archetype ID
        new_blocklist (list): New block list to use for client archetype

    Returns:
        tuple[bool, str]: success & message
    """
    for item in new_blocklist:
        if not ResearchPointType.has_value(item):
            return False, "Invalid research point type found: {}".format(item)

    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        return False, "Client archetype not found"

    ca.transformer_blocklist = new_blocklist
    db.session.add(ca)
    db.session.commit()

    return True, "OK"


def replicate_transformer_blocklist(
    source_client_archetype_id: int, destination_client_archetype_id: int
) -> any:
    """Replicates the source client archetype's transformer blocklist to destination client archetype

    Args:
        source_client_archetype_id (int): id of client archetype to copy
        destination_client_archetype_id (int): id of client archetype to paste to

    Returns:
        tuple[bool, str]: success & message
    """
    source_ca: ClientArchetype = ClientArchetype.query.get(source_client_archetype_id)
    if not source_ca:
        return False, "Source client archetype not found"
    destination_ca: ClientArchetype = ClientArchetype.query.get(
        destination_client_archetype_id
    )
    if not destination_ca:
        return False, "Destination client archetype not found"

    destination_ca.transformer_blocklist = source_ca.transformer_blocklist
    db.session.add(destination_ca)
    db.session.commit()

    return True, "OK"


def get_archetype_details_for_sdr(client_sdr_id: int):
    """
    Given a client sdr id, return the archetype details.

    Details look like so:
    [
        {
            id: (int) client archetype id,
            name: (str) client archetype name,
            active: (bool) if the client archetype is active,
            num_prospects: (int) number of prospects with this archetype
            num_unused_li_prospects: (int) number of prospects with this archetype that are unused LI prospects
            num_unused_email_prospects: (int) number of prospects with this archetype that are unused email prospects
            percent_unused_li_prospects: (float) percent of prospects with this archetype that are unused LI prospects
            percent_unused_email_prospects: (float) percent of prospects with this archetype that are unused email prospects
        },
        ...
    ]
    """

    query = """
        select
            client_archetype.id,
            client_archetype.archetype "name",
            client_archetype.active,
            count(distinct prospect.id) "num_prospects",
            count(distinct prospect.id) filter (where prospect.approved_outreach_message_id is null) "num_unused_li_prospects",
            count(distinct prospect.id) filter (where prospect.approved_prospect_email_id is null)"num_unused_email_prospects",
            cast(count(distinct prospect.id) filter (where prospect.approved_outreach_message_id is null) as float) / (count(distinct prospect.id) + 0.0001) "percent_unused_li_prospects",
            cast(count(distinct prospect.id) filter (where prospect.approved_prospect_email_id is null) as float) / (count(distinct prospect.id)+ 0.0001) "percent_unused_li_prospects"
        from client_archetype
            left join prospect on prospect.archetype_id = client_archetype.id
        where client_archetype.client_sdr_id = {client_sdr_id}
        group by 1,2,3
        order by active desc, archetype desc;
    """.format(
        client_sdr_id=client_sdr_id
    )

    data = db.session.execute(query).fetchall()
    list_of_archetypes = []
    for entry in data:
        list_of_archetypes.append(
            {
                "id": entry[0],
                "name": entry[1],
                "active": entry[2],
                "num_prospects": entry[3],
                "num_unused_li_prospects": entry[4],
                "num_unused_email_prospects": entry[5],
                "percent_unused_li_prospects": entry[6],
                "percent_unused_email_prospects": entry[7],
            }
        )

    return list_of_archetypes


def create_empty_archetype_prospect_filters(
    client_sdr_id: int, archetype_id: int
) -> bool:
    """Creates an empty archetype prospect filter for the given archetype id

    Args:
        client_sdr_id (int): ID of client sdr
        archetype_id (int): ID of archetype

    Returns:
        bool: True if successful, False if not
    """
    ca: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not ca:
        return False

    empty_filter: dict = {
        "lead": {
            "company": {
                "current_company_names_inclusion": [],
                "current_company_names_exclusion": [],
                "past_company_names_inclusion": [],
                "past_company_names_exclusion": [],
            },
            "role": {
                "current_job_title_inclusion": [],
                "current_job_title_exclusion": [],
                "past_job_title_inclusion": [],
                "past_job_title_exclusion": [],
                "current_job_function_inclusion": [],
                "current_job_function_exclusion": [],
                "seniority_inclusion": [],
                "seniority_exclusion": [],
                "years_in_current_company": [],
                "years_in_current_position": [],
            },
            "personal": {
                "geography_inclusion": [],
                "geography_exclusion": [],
                "industry_inclusion": [],
                "industry_exclusion": [],
                "years_of_experience": [],
            },
        },
        "account": {
            "annual_revenue": [],
            "headcount": [],
            "headquarter_location_inclusion": [],
            "headquarter_location_exclusion": [],
            "account_industry_inclusion": [],
            "account_industry_exclusion": [],
        },
    }

    ca.prospect_filters = empty_filter
    db.session.add(ca)
    db.session.commit()

    return True


def modify_archetype_prospect_filters(
    client_sdr_id: int,
    archetype_id: int,
    current_company_names_inclusion: Optional[list] = [],
    current_company_names_exclusion: Optional[list] = [],
    past_company_names_inclusion: Optional[list] = [],
    past_company_names_exclusion: Optional[list] = [],
    current_job_title_inclusion: Optional[list] = [],
    current_job_title_exclusion: Optional[list] = [],
    past_job_title_inclusion: Optional[list] = [],
    past_job_title_exclusion: Optional[list] = [],
    current_job_function_inclusion: Optional[list] = [],
    current_job_function_exclusion: Optional[list] = [],
    seniority_inclusion: Optional[list] = [],
    seniority_exclusion: Optional[list] = [],
    years_in_current_company: Optional[list] = [],
    years_in_current_position: Optional[list] = [],
    geography_inclusion: Optional[list] = [],
    geography_exclusion: Optional[list] = [],
    industry_inclusion: Optional[list] = [],
    industry_exclusion: Optional[list] = [],
    years_of_experience: Optional[list] = [],
    annual_revenue: Optional[list] = [],
    headcount: Optional[list] = [],
    headquarter_location_inclusion: Optional[list] = [],
    headquarter_location_exclusion: Optional[list] = [],
    account_industry_inclusion: Optional[list] = [],
    account_industry_exclusion: Optional[list] = [],
) -> bool:
    """
    Modify the prospect filters for a given archetype

    Args:
        client_sdr_id (int): client sdr id
        archetype_id (int): archetype id
        ...

    Returns:
        bool: success
    """
    ca: ClientArchetype = ClientArchetype.query.filter_by(
        client_sdr_id=client_sdr_id, id=archetype_id
    ).first()
    if not ca:
        return False

    original_filters: dict = ca.prospect_filters
    if not original_filters:
        create_empty_archetype_prospect_filters(client_sdr_id, archetype_id)

    new_filters: dict = {
        "lead": {
            "company": {
                "current_company_names_inclusion": current_company_names_inclusion,
                "current_company_names_exclusion": current_company_names_exclusion,
                "past_company_names_inclusion": past_company_names_inclusion,
                "past_company_names_exclusion": past_company_names_exclusion,
            },
            "role": {
                "current_job_title_inclusion": current_job_title_inclusion,
                "current_job_title_exclusion": current_job_title_exclusion,
                "past_job_title_inclusion": past_job_title_inclusion,
                "past_job_title_exclusion": past_job_title_exclusion,
                "current_job_function_inclusion": current_job_function_inclusion,
                "current_job_function_exclusion": current_job_function_exclusion,
                "seniority_inclusion": seniority_inclusion,
                "seniority_exclusion": seniority_exclusion,
                "years_in_current_company": years_in_current_company,
                "years_in_current_position": years_in_current_position,
            },
            "personal": {
                "geography_inclusion": geography_inclusion,
                "geography_exclusion": geography_exclusion,
                "industry_inclusion": industry_inclusion,
                "industry_exclusion": industry_exclusion,
                "years_of_experience": years_of_experience,
            },
        },
        "account": {
            "annual_revenue": annual_revenue,
            "headcount": headcount,
            "headquarter_location_inclusion": headquarter_location_inclusion,
            "headquarter_location_exclusion": headquarter_location_exclusion,
            "account_industry_inclusion": account_industry_inclusion,
            "account_industry_exclusion": account_industry_exclusion,
        },
    }

    sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()

    send_slack_message(
        message=f"SDR {sdr.name} has modified the prospect filters for archetype {ca.archetype}!",
        webhook_urls=[URL_MAP.get("operations-persona-filters")],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "SDR *{sdr_name}* has modified the prospect filters for archetype *{archetype_name}*!".format(
                        sdr_name=sdr.name, archetype_name=ca.archetype
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Next steps: Validate and apply the changes.",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*SellScale Sight*: <{link}|Link>".format(
                        link="https://app.sellscale.com/authenticate?stytch_token_type=direct&token="
                        + sdr.auth_token
                    ),
                },
            },
        ],
    )

    ca.prospect_filters = new_filters
    db.session.add(ca)
    db.session.commit()

    return True


def get_email_blocks_configuration(
    client_sdr_id: int,
    client_archetype_id: int,
    email_bump_framework_id: Optional[int] = None,
) -> list:
    """Get the email blocks configuration for a given archetype and/or bump_framework ID

    Args:
        client_sdr_id (int): client sdr id
        client_archetype_id (int): client archetype id
        email_bump_framework_id (int, optional): email bump framework id. Defaults to None.

    Returns:
        list: email blocks configuration
    """
    from src.email_sequencing.models import EmailSequenceStep

    sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    if not sdr:
        return []

    archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()
    if not archetype:
        return []
    if archetype.client_sdr_id != sdr.id:
        return []

    if archetype.email_blocks_configuration is None:
        create_default_archetype_email_blocks_configuration(
            client_sdr_id, client_archetype_id
        )

    if email_bump_framework_id:
        bf_email: EmailSequenceStep = EmailSequenceStep.query.get(
            email_bump_framework_id
        )
        if not bf_email:
            return []
        if bf_email.client_archetype_id != archetype.id:
            return []
        return bf_email.email_blocks

    return archetype.email_blocks_configuration


def create_default_archetype_email_blocks_configuration(
    client_sdr_id: int, client_archetype_id: int
) -> bool:
    """Create an empty email blocks configuration for a given archetype

    Args:
        client_sdr_id (int): client sdr id
        client_archetype_id (int): client archetype id

    Returns:
        bool: success
    """
    sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    if not sdr:
        return False

    archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()
    if not archetype:
        return False
    if archetype.client_sdr_id != sdr.id:
        return False

    archetype.email_blocks_configuration = [
        "Personalize the title to their company and or the prospect",
        "Include a greeting with Hi, Hello, or Hey with their first name",
        "Personalized 1-2 lines. Mentioned details about them, their role, their company, or other relevant pieces of information. Use personal details about them to be natural and personal.",
        "Mention what we do and offer and how it can help them based on their background, company, and key details.",
        "Use the objective for a call to action",
        "End with Best, (new line) (My Name) (new line) (Title)",
    ]
    db.session.add(archetype)
    db.session.commit()

    return True


def patch_archetype_email_blocks_configuration(
    client_sdr_id: int, client_archetype_id: int, blocks: list[str]
) -> tuple[bool, str]:
    """Patch the email blocks configuration for a given archetype

    Args:
        blocks (list[str]): list of blocks

    Returns:
        tuple[bool, str]: success, message
    """
    sdr: ClientSDR = ClientSDR.query.filter_by(id=client_sdr_id).first()
    if not sdr:
        return False, "Client SDR not found"

    archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=client_archetype_id
    ).first()
    if not archetype:
        return False, "Client archetype not found"
    if archetype.client_sdr_id != sdr.id:
        return False, "Client SDR does not own this archetype"

    archetype.email_blocks_configuration = blocks
    db.session.add(archetype)
    db.session.commit()

    return True


def activate_client_archetype(client_sdr_id: int, client_archetype_id: int) -> bool:
    """Activate a client archetype.

    Args:
        client_sdr_id (int): Client SDR ID
        client_archetype_id (int): Client archetype ID

    Returns:
        bool: success
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not archetype:
        return False
    if archetype.client_sdr_id != sdr.id:
        return False

    # Mark the archetype as active
    archetype.active = True
    db.session.commit()

    # Bulk update prospects
    update_statement = (
        update(Prospect)
        .where(Prospect.archetype_id == archetype.id)
        .values(active=True)
    )
    db.session.execute(update_statement)
    db.session.commit()

    return True


def deactivate_client_archetype(client_sdr_id: int, client_archetype_id: int) -> bool:
    """Deactivate a client archetype.

    Args:
        client_sdr_id (int): Client SDR ID
        client_archetype_id (int): Client archetype ID

    Returns:
        bool: success
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not archetype:
        return False
    if archetype.client_sdr_id != sdr.id:
        return False

    archetype.active = False
    db.session.commit()

    return True


def hard_deactivate_client_archetype(
    client_sdr_id: int, client_archetype_id: int
) -> bool:
    """Hard deactivate a client archetype. This will also block messages and mark the prospects as inactive.

    Args:
        client_sdr_id (int): client sdr id
        client_archetype_id (int): client archetype id

    Returns:
        bool: success
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not archetype:
        return False
    if archetype.client_sdr_id != sdr.id:
        return False

    # Set archetype to no longer active
    archetype.active = False
    db.session.commit()

    # Collect bulk save objects list for efficient update

    # Get all prospects that are in this archetype that are in the PROSPECTED state
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.archetype_id == archetype.id
    ).all()

    for prospect in prospects:
        # Mark prospect as no longer active
        prospect.active = False

        # If the prospect is in a status PROSPECTED or QUEUED_FOR_OUTREACH, we need to block and wipe the messages
        if (
            prospect.status == ProspectStatus.PROSPECTED
            or prospect.status == ProspectStatus.QUEUED_FOR_OUTREACH
        ):

            # If the prospect has a generated message, mark it as BLOCKED and remove the ID from Prospect
            if prospect.approved_outreach_message_id:
                gm: GeneratedMessage = GeneratedMessage.query.get(
                    prospect.approved_outreach_message_id
                )
                gm.message_status = GeneratedMessageStatus.BLOCKED
                prospect.approved_outreach_message_id = None

            # If the prospect has a email component, grab the generated message and mark it as BLOCKED and remove the ID from ProspectEmail
            if prospect.approved_prospect_email_id:
                p_email: ProspectEmail = ProspectEmail.query.get(
                    prospect.approved_prospect_email_id
                )
                subject: GeneratedMessage = GeneratedMessage.query.get(
                    p_email.personalized_subject_line
                )
                if subject:
                    subject.message_status = GeneratedMessageStatus.BLOCKED
                    p_email.personalized_subject_line = None
                first_line: GeneratedMessage = GeneratedMessage.query.get(
                    p_email.personalized_first_line
                )
                if first_line:
                    first_line.message_status = GeneratedMessageStatus.BLOCKED
                    p_email.personalized_first_line = None
                body: GeneratedMessage = GeneratedMessage.query.get(
                    p_email.personalized_body
                )
                if body:
                    body.message_status = GeneratedMessageStatus.BLOCKED
                    p_email.personalized_body = None

    db.session.commit()

    return True


def move_prospects_to_archetype(
    client_sdr_id: int, target_archetype_id: int, prospect_ids: list[int]
):
    """Move prospects from one archetype to another.

    Args:
        client_sdr_id (int): client sdr id
        target_archetype_id (int): target archetype id

    Returns:
        bool: success
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False

    target_archetype: ClientArchetype = ClientArchetype.query.get(target_archetype_id)
    if not target_archetype:
        return False
    if target_archetype.client_sdr_id != sdr.id:
        return False

    # Get all prospects that are in this archetype that are in the PROSPECTED state
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_ids)
    ).all()

    for prospect in prospects:
        # Reassign the prospect to the new archetype
        prospect.archetype_id = target_archetype.id

    db.session.commit()

    # Re-classify the prospects
    for index, prospect_id in enumerate(prospect_ids):
        countdown = float(index * 6)
        mark_queued_and_classify.apply_async(
            args=[client_sdr_id, target_archetype_id, prospect_id, countdown],
            queue="ml_prospect_classification",
            routing_key="ml_prospect_classification",
            priority=5,
        )

    return True
