from datetime import datetime
from src.analytics.services import get_all_campaign_analytics_for_client
from src.company.models import Company
from sqlalchemy import update
from app import db, celery
from model_import import ClientArchetype
from typing import Union, Optional
from src.client.models import Client, ClientAssets, ClientSDR, EmailToLinkedInConnection
from src.email_outbound.models import ProspectEmail, ProspectEmailStatus
from src.email_sequencing.services import get_email_sequence_step_for_sdr
from src.message_generation.models import GeneratedMessage, GeneratedMessageStatus
from src.prospecting.icp_score.services import move_selected_prospects_to_unassigned
from src.prospecting.models import Prospect, ProspectOverallStatus, ProspectStatus
from src.simulation.models import SimulationRecord
from src.li_conversation.models import (
    LinkedinInitialMessageTemplate,
)
from src.simulation.services import generate_entire_simulated_conversation
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
)
from src.smartlead.smartlead import Smartlead
from src.bump_framework.services import get_all_bump_framework_assets

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
    # for item in new_blocklist:
    #     if not ResearchPointType.has_value(item):
    #         return False, "Invalid research point type found: {}".format(item)

    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        return False, "Client archetype not found"

    ca.transformer_blocklist = new_blocklist
    db.session.add(ca)
    db.session.commit()

    return True, "OK"


def update_transformer_blocklist_initial(
    client_archetype_id: int, new_blocklist: list
) -> any:
    """
    Set's the client archetype's initial transformer blocker

    Args:
        client_archetype_id (int): Client Archetype ID
        new_blocklist (list): New block list to use for client archetype

    Returns:
        tuple[bool, str]: success & message
    """
    # for item in new_blocklist:
    #     if not ResearchPointType.has_value(item):
    #         return False, "Invalid research point type found: {}".format(item)

    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        return False, "Client archetype not found"

    ca.transformer_blocklist_initial = new_blocklist
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
            count(distinct prospect.id) filter (where prospect.approved_outreach_message_id is null and prospect.overall_status = 'PROSPECTED') "num_unused_li_prospects",
            count(distinct prospect.id) filter (where prospect.approved_prospect_email_id is null) "num_unused_email_prospects",
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


def get_archetype_activity(client_sdr_id: int) -> list[dict]:
    interval = "1 day"

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = sdr.client_id

    results = db.session.execute(
        """
        SELECT
            count(DISTINCT prospect.id) FILTER (
                WHERE
                    (
                        prospect_status_records.to_status = 'SENT_OUTREACH'
                        AND prospect_status_records.created_at > now() - '{interval}'::interval
                    )
                    OR
                    (
                        prospect_email_status_records.to_status = 'SENT_OUTREACH'
                        AND prospect_email_status_records.created_at > now() - '{interval}'::interval
                    )
            ) "messages_sent",
            count(DISTINCT prospect.id) FILTER (
                WHERE
                    (
                        linkedin_conversation_entry.date > now() - '{interval}'::interval
                        AND linkedin_conversation_entry.ai_generated
                        AND prospect.overall_status IN ('ACCEPTED', 'BUMPED')
                    ) OR (
                    	prospect_email_status_records.created_at > now() - '{interval}'::interval
                        AND prospect_email_status_records.to_status = 'EMAIL_OPENED'
                    )
            ) "bumps_sent",
            count(DISTINCT linkedin_conversation_entry.id) FILTER (
                WHERE linkedin_conversation_entry.date > now() - '{interval}'::interval
                AND linkedin_conversation_entry.ai_generated
                AND prospect.overall_status IN ('ACTIVE_CONVO')
            ) "replies_sent"
        FROM
            prospect
            LEFT JOIN linkedin_conversation_entry ON linkedin_conversation_entry.thread_urn_id = prospect.li_conversation_urn_id
            LEFT JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id
            LEFT JOIN prospect_email on prospect_email.prospect_id = prospect.id
            LEFT JOIN prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
        WHERE client_id = {client_id};
        """.format(
            interval=interval, client_id=client_id
        )
    ).fetchall()

    # Index to column
    column_map = {
        0: "messages_sent",
        1: "bumps_sent",
        2: "replies_sent",
    }

    # Convert and format output
    results = [
        {column_map.get(i, "unknown"): value for i, value in enumerate(tuple(row))}
        for row in results
    ]

    return results


def overall_activity_for_client(client_sdr_id: int):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = sdr.client_id

    def li_stats():
        query = """
            select
              count(*) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') sent_outreach,
              count(*) filter (where prospect_status_records.to_status = 'ACCEPTED') email_opened,
              count(*) filter (where prospect_status_records.to_status = 'ACTIVE_CONVO') active_convo,
              count(*) filter (where prospect_status_records.to_status = 'DEMO_SET') demo_set
            from prospect left join prospect_status_records on prospect_status_records.prospect_id = prospect.id where prospect.client_id = {client_id};
        """.format(
            client_id=client_id
        )

        data = db.session.execute(query).fetchall()

        column_map = {
            0: "sent_outreach",
            1: "email_opened",
            2: "active_convo",
            3: "demo_set",
        }

        # Convert and format output
        results = [
            {column_map.get(i, "unknown"): value for i, value in enumerate(tuple(row))}
            for row in data
        ]
        return results

    def email_stats():
        query = """
          select
            count(*) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') sent_outreach,
            count(*) filter (where prospect_email_status_records.to_status = 'EMAIL_OPENED') email_opened,
            count(*) filter (where prospect_email_status_records.to_status = 'ACTIVE_CONVO') active_convo,
            count(*) filter (where prospect_email_status_records.to_status = 'DEMO_SET') demo_set
          from prospect_email left join prospect on prospect.id = prospect_email.prospect_id left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id where prospect.client_id = {client_id};
        """.format(
            client_id=client_id
        )

        data = db.session.execute(query).fetchall()

        column_map = {
            0: "sent_outreach",
            1: "email_opened",
            2: "active_convo",
            3: "demo_set",
        }

        # Convert and format output
        results = [
            {column_map.get(i, "unknown"): value for i, value in enumerate(tuple(row))}
            for row in data
        ]
        return results

    li = li_stats()
    email = email_stats()

    return {
        "li": li,
        "email": email,
        "merged": {
            "sent_outreach": li[0]["sent_outreach"] + email[0]["sent_outreach"],
            "email_opened": li[0]["email_opened"] + email[0]["email_opened"],
            "active_convo": li[0]["active_convo"] + email[0]["active_convo"],
            "demo_set": li[0]["demo_set"] + email[0]["demo_set"],
        },
    }


def get_archetype_conversion_rates(client_sdr_id: int, archetype_id: int) -> dict:
    results = db.session.execute(
        """
        SELECT
            client_archetype.archetype,
            client_archetype.id,
            client_archetype.created_at,
            client_archetype.active,
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'SENT_OUTREACH') "EMAIL-SENT",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'EMAIL_OPENED') "EMAIL-OPENED",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_email_status_records.to_status = 'ACTIVE_CONVO') "EMAIL-REPLY",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'SENT_OUTREACH') "LI-SENT",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'ACCEPTED') "LI-OPENED",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'ACTIVE_CONVO') "LI-REPLY",
            count(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status in ('DEMO_SET', 'DEMO_WON')) "LI-DEMO",
            client_archetype.emoji
        FROM
            client_archetype
            LEFT JOIN prospect ON prospect.archetype_id = client_archetype.id
            LEFT JOIN prospect_email ON prospect_email.id = prospect.approved_prospect_email_id
            LEFT JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id
            LEFT JOIN prospect_email_status_records ON prospect_email_status_records.prospect_email_id = prospect_email.id
        WHERE
            client_archetype.id = {archetype_id}
            AND client_archetype.client_sdr_id = {client_sdr_id}
            AND client_archetype.is_unassigned_contact_archetype != TRUE
        GROUP BY
            2;
        """.format(
            archetype_id=archetype_id, client_sdr_id=client_sdr_id
        )
    ).fetchone()

    # index to column
    column_map = {
        0: "name",
        1: "id",
        2: "created_at",
        3: "active",
        4: "emails_sent",
        5: "emails_opened",
        6: "emails_replied",
        7: "li_sent",
        8: "li_opened",
        9: "li_replied",
        10: "li_demo",
        11: "emoji",
    }

    # Convert and format output
    result = {column_map.get(i, "unknown"): value for i, value in enumerate(results)}

    return result


def get_archetype_details(archetype_id: int) -> dict:
    if not archetype_id:
        return {}

    results = db.session.execute(
        """
        SELECT
            client_archetype.archetype,
            client_archetype.id,
            client_archetype.created_at,
            client_archetype.active
        FROM
            client_archetype
        WHERE
            client_archetype.id = {archetype_id};
        """.format(
            archetype_id=archetype_id
        )
    ).fetchone()

    # index to column
    column_map = {0: "name", 1: "id", 2: "created_at", 3: "active"}

    # Convert and format output
    result = {column_map.get(i, "unknown"): value for i, value in enumerate(results)}

    return result


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
    archetype.setup_status = "ACTIVE"
    db.session.commit()

    # Bulk update prospects
    update_statement = (
        update(Prospect)
        .where(Prospect.archetype_id == archetype.id)
        .values(active=True)
    )
    db.session.execute(update_statement)
    db.session.commit()

    # If this campaign is tied to Smartlead, then we need to START the campaign
    if archetype.smartlead_campaign_id:
        sl = Smartlead()
        sl.post_campaign_status(
            campaign_id=archetype.smartlead_campaign_id, status="START"
        )

    return True


def deactivate_client_archetype(
    client_sdr_id: int, client_archetype_id: int, autodetected: Optional[bool] = False, turnOffSmartleadCampaign: Optional[bool] = True
) -> bool:
    """Deactivate a client archetype.

    Args:
        client_sdr_id (int): Client SDR ID
        client_archetype_id (int): Client archetype ID
        autodetected (bool, optional): If True, means that this was autodetected. Defaults to False.

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
    archetype.linkedin_active = False
    archetype.email_active = False
    archetype.setup_status = "INACTIVE"
    db.session.commit()

    # If this campaign is tied to Smartlead, then we need to PAUSE the campaign
    if autodetected:
        if archetype.smartlead_campaign_id and turnOffSmartleadCampaign:
            sl = Smartlead()
            sl.post_campaign_status(
                campaign_id=archetype.smartlead_campaign_id, status="PAUSED"
            )

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
    archetype.setup_status = "INACTIVE"
    db.session.commit()

    # Collect bulk save objects list for efficient update

    # Get all prospects that are in this archetype that are in the PROSPECTED state
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.archetype_id == archetype.id
    ).all()

    for prospect in prospects:
        # Mark prospect as no longer active
        prospect.active = False

        # LINKEDIN: If the prospect is in a status PROSPECTED or QUEUED_FOR_OUTREACH, we need to block and wipe the messages
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

        # EMAIL: If the prospect has a email component, we need to check if the status of the prospect email is not SENT (i.e. it's still in the queue)
        # Then we should grab the generated message and mark it as BLOCKED and remove the ID from ProspectEmail
        if prospect.approved_prospect_email_id:
            p_email: ProspectEmail = ProspectEmail.query.get(
                prospect.approved_prospect_email_id
            )
            if p_email.email_status != ProspectEmailStatus.SENT:
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

    prospected_prospects: list[Prospect] = Prospect.query.filter(
        Prospect.archetype_id == archetype.id,
        Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
    ).all()
    prospect_ids = [prospect.id for prospect in prospected_prospects]
    move_selected_prospects_to_unassigned(
        prospect_ids=prospect_ids,
    )

    # If this campaign is tied to Smartlead, then we need to STOP the campaign
    if archetype.smartlead_campaign_id:
        sl = Smartlead()
        sl.post_campaign_status(
            campaign_id=archetype.smartlead_campaign_id, status="STOPPED"
        )

    return True


def get_icp_filters_autofill(client_sdr_id: int, client_archetype_id: int):
    """
    Gets the top values for each filter in the ICP filters to use as autofill
    """

    AMOUNT = 10

    # Top 10 job titles
    results = db.session.execute(
        f"""
        select lower(title), count(distinct prospect.id) from prospect where archetype_id = {client_archetype_id} group by 1 order by 2 desc limit {AMOUNT};
        """
    ).fetchall()
    job_titles = [result[0] for result in results]

    # Top 10 industries
    results = db.session.execute(
        f"""
        select lower(industry), count(distinct prospect.id) from prospect where archetype_id = {client_archetype_id} group by 1 order by 2 desc limit {AMOUNT};
      """
    ).fetchall()
    industries = [result[0] for result in results]

    # Get average years of experience
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id
    ).all()
    mins = []
    maxes = []
    for prospect in prospects:
        if prospect.employee_count:
            parts = prospect.employee_count.split("-")
            if len(parts) == 2:
                try:
                    mins.append(int(parts[0]))
                    maxes.append(int(parts[1]))
                except ValueError:
                    pass
    avg_min = sum(mins) / (len(mins) + 0.0001)
    avg_max = sum(maxes) / (len(maxes) + 0.0001)

    return {
        "job_titles": job_titles,
        "industries": industries,
        "yoe": {
            "min": avg_min,
            "max": avg_max,
        },
    }


def get_client_archetype_stats(client_archetype_id):
    archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    client_sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
    client_id = archetype.client_id
    num_prospects: int = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id
    ).count()
    num_prospects_with_emails: int = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id,
        Prospect.email.isnot(None),
    ).count()

    sample_prospects = (
        Prospect.query.filter(
            Prospect.archetype_id == client_archetype_id,
            # overall status is not ACTIVE_CONVO, DEMO_SET, NURTURE, or REMOVED
            Prospect.overall_status.notin_(
                [
                    ProspectOverallStatus.ACTIVE_CONVO,
                    ProspectOverallStatus.DEMO,
                    ProspectOverallStatus.REMOVED,
                    ProspectOverallStatus.NURTURE,
                ]
            ),
            Prospect.icp_fit_score > 0,
        )
        .order_by(Prospect.icp_fit_score.desc())
        .limit(20)
    )

    analytics = get_all_campaign_analytics_for_client(
        client_id=client_id,
        client_archetype_id=int(client_archetype_id),
    )

    # Overall Campaign Details
    emoji = archetype.emoji
    archetype_name = archetype.archetype
    sdr_name = client_sdr.name

    num_sent, num_opens, num_replies, num_demos = 0, 0, 0, 0
    included_individual_title_keywords = []
    included_individual_seniority_keywords = []
    included_individual_locations_keywords = []
    included_individual_industry_keywords = []
    included_individual_generalized_keywords = []
    included_individual_skills_keywords = []
    included_company_name_keywords = []
    included_company_locations_keywords = []
    included_company_generalized_keywords = []
    included_company_industries_keywords = []

    if analytics and len(analytics) > 0:
        num_sent = analytics[0]["num_sent"]
        num_opens = analytics[0]["num_opens"]
        num_replies = analytics[0]["num_replies"]
        num_demos = analytics[0]["num_demos"]

        included_individual_title_keywords = analytics[0][
            "included_individual_title_keywords"
        ]
        included_individual_seniority_keywords = analytics[0][
            "included_individual_seniority_keywords"
        ]
        included_individual_locations_keywords = analytics[0][
            "included_individual_locations_keywords"
        ]
        included_individual_industry_keywords = analytics[0][
            "included_individual_industry_keywords"
        ]
        included_individual_generalized_keywords = analytics[0][
            "included_individual_generalized_keywords"
        ]
        included_individual_skills_keywords = analytics[0][
            "included_individual_skills_keywords"
        ]
        included_company_name_keywords = analytics[0]["included_company_name_keywords"]
        included_company_locations_keywords = analytics[0][
            "included_company_locations_keywords"
        ]
        included_company_generalized_keywords = analytics[0][
            "included_company_generalized_keywords"
        ]
        included_company_industries_keywords = analytics[0][
            "included_company_industries_keywords"
        ]

    # top titles
    def get_top_attributes_list(attribute):
        query = """
            select
                {attribute} attribute, count(*) count
            from prospect
            where prospect.archetype_id = {client_archetype_id}
            group by 1
            order by 2 desc
            limit 10;
        """.format(
            attribute=attribute, client_archetype_id=client_archetype_id
        )
        data = db.session.execute(query).fetchall()
        return [dict(row) for row in data]

    # Email Details
    email_sequence = get_email_sequence_step_for_sdr(
        client_sdr_id=client_sdr.id,
        overall_statuses=[
            ProspectOverallStatus.PROSPECTED,
            ProspectOverallStatus.SENT_OUTREACH,
            ProspectOverallStatus.ACCEPTED,
            ProspectOverallStatus.BUMPED,
        ],
        client_archetype_ids=[client_archetype_id],
        activeOnly=True,
    )

    def sort_func(x):
        bumped_count = x["step"]["bumped_count"]
        overall_status = x["step"]["overall_status"]

        if overall_status == "PROSPECTED":
            return 0
        elif overall_status == "ACCEPTED":
            return 1
        elif overall_status == "BUMPED":
            return bumped_count + 2
        else:
            return 20

    email_sequence = sorted(email_sequence, key=sort_func)

    # Variants Edge Case:
    #   There may be email_sequence steps that have same bumped_count and overall_status. I only want one of each combo. Use set + for loop to filter it out
    unique_bump_count_overall_status = set()
    filtered_email_sequence = []
    for step_data in email_sequence:
        bumped_count = step_data["step"]["bumped_count"]
        overall_status = step_data["step"]["overall_status"]
        if (bumped_count, overall_status) not in unique_bump_count_overall_status:
            unique_bump_count_overall_status.add((bumped_count, overall_status))
            filtered_email_sequence.append(step_data)

    email_sequence = [
        {
            "title": step_data["step"]["title"],
            "description": step_data["step"]["template"],
            "bumped_count": step_data["step"]["bumped_count"],
            "overall_status": step_data["step"]["overall_status"],
            "assets": step_data["assets"],
        }
        for step_data in filtered_email_sequence
    ]

    # Linkedin sequence
    # success, records = generate_entire_simulated_conversation(
    #     archetype_id=client_archetype_id,
    # )
    success = False
    if success:
        simulation_records: list[SimulationRecord] = records
        linkedin_sequence = []
        for i, record in enumerate(simulation_records):
            entry = {
                "title": (
                    record.meta_data.get("bump_framework_title")
                    if i > 0
                    else "Invite Message"
                ),
                "description": record.data.get("message"),
                "bumped_count": i - 1,
                "bump_framework_delay": record.meta_data
                and record.meta_data.get("bump_framework_delay")
                or 0,
                "bump_framework_id": record.meta_data.get("bump_framework_id"),
            }
            linkedin_sequence.append(entry)
    else:
        query = """
            select
                id,
                title,
                description,
                bumped_count
            from
                bump_framework
            where client_archetype_id = {client_archetype_id}
                and overall_status in ('ACCEPTED', 'BUMPED')
                and bump_framework.active
            order by
                bumped_count asc;
        """.format(
            client_archetype_id=client_archetype_id
        )
        data = db.session.execute(query).fetchall()
        linkedin_sequence = [
            {
                "bump_framework_id": row[0],
                "title": row[1],
                "description": "Instruction: " + str(row[2]),
                "bumped_count": row[3],
            }
            for row in data
        ]

    # Get all assets for the bf in the linkedin sequence
    for i, entry in enumerate(linkedin_sequence):
        bf_id = entry.get("bump_framework_id")
        if bf_id:
            entry["assets"] = get_all_bump_framework_assets(bf_id)

    return {
        "overview": {
            "emoji": emoji,
            "archetype_name": archetype_name,
            "sdr_name": sdr_name,
            "num_sent": num_sent,
            "num_opens": num_opens,
            "num_replies": num_replies,
            "num_demos": num_demos,
            "num_prospects": num_prospects,
            "num_prospects_with_emails": num_prospects_with_emails,
        },
        "contacts": {
            "included_individual_title_keywords": included_individual_title_keywords,
            "included_individual_locations_keywords": included_individual_locations_keywords,
            "included_individual_seniority_keywords": included_individual_seniority_keywords,
            "included_individual_industry_keywords": included_individual_industry_keywords,
            "included_individual_generalized_keywords": included_individual_generalized_keywords,
            "included_individual_skills_keywords": included_individual_skills_keywords,
            "included_company_name_keywords": included_company_name_keywords,
            "included_company_locations_keywords": included_company_locations_keywords,
            "included_company_generalized_keywords": included_company_generalized_keywords,
            "included_company_industries_keywords": included_company_industries_keywords,
            "sample_contacts": [p.to_dict() for p in sample_prospects],
        },
        "linkedin": {"sequence": linkedin_sequence},
        "email": {"sequence": email_sequence},
        "assets_used": fetch_archetype_assets(client_archetype_id),
        "top_attributes": {
            "top_titles": get_top_attributes_list("title"),
            "top_industries": get_top_attributes_list("industry"),
            "top_companies": get_top_attributes_list("company"),
        },
    }

def get_client_archetype_analytics(client_archetype_id):
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    client_id = client_archetype.client_id

    analytics = get_all_campaign_analytics_for_client(
        client_id=client_id,
        client_archetype_id=int(client_archetype_id),
    )

    num_sent, num_opens, num_replies, num_demos, num_pos_replies = 0, 0, 0, 0, 0
    if analytics and len(analytics) > 0:
        num_sent = analytics[0]["num_sent"]
        num_opens = analytics[0]["num_opens"]
        num_replies = analytics[0]["num_replies"]
        num_demos = analytics[0]["num_demos"]
        num_pos_replies = analytics[0]["num_pos_replies"]


    return {
        "num_sent": num_sent,
        "num_opens": num_opens,
        "num_replies": num_replies,
        "num_demos": num_demos,
        "num_pos_replies": num_pos_replies,
    }


def get_client_archetype_overview(client_archetype_id):
    archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    client_sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
    client_id = archetype.client_id


    emoji = archetype.emoji
    archetype_name = archetype.archetype
    ai_researcher_id = archetype.ai_researcher_id
    sdr_name = client_sdr.name
    sdr_img_url = client_sdr.img_url
    created_at = archetype.created_at
    email_to_linkedin_connection = archetype.email_to_linkedin_connection.value if archetype.email_to_linkedin_connection else None
    email_active = archetype.email_active
    active = archetype.active
    linkedin_active = archetype.linkedin_active
    testing_volume = archetype.testing_volume
    id = archetype.id

    num_prospects: int = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id
    ).count()
    num_prospects_with_emails: int = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id,
        Prospect.email.isnot(None),
    ).count()

    return {
        "id": id,
        "emoji": emoji,
        "archetype_name": archetype_name,
        "sdr_name": sdr_name,
        "sdr_img_url": sdr_img_url,
        "created_at": created_at,
        "ai_researcher_id": ai_researcher_id,
        "email_active": email_active,
        "active": active,
        "is_setting_up": archetype.is_setting_up,
        "email_to_linkedin_connection": email_to_linkedin_connection,
        "linkedin_active": linkedin_active,
        "testing_volume": testing_volume,
        "num_prospects": num_prospects,
        "num_prospects_with_emails": num_prospects_with_emails,
        "is_ai_research_personalization_enabled": archetype.is_ai_research_personalization_enabled,
        "setup_status": archetype.setup_status.value if archetype.setup_status else None,
    }

def get_total_contacts_for_archetype(client_archetype_id):
    num_prospects: int = Prospect.query.filter(
        Prospect.archetype_id == client_archetype_id
    ).count()

    return {
        "num_prospects": num_prospects,
    }

def get_client_archetype_contacts(client_archetype_id, offset=0, limit=20, text="", include_analytics=True):
    filters = [
        Prospect.archetype_id == client_archetype_id,
        Prospect.overall_status.notin_([
            ProspectOverallStatus.ACTIVE_CONVO,
            ProspectOverallStatus.DEMO,
            ProspectOverallStatus.REMOVED,
            ProspectOverallStatus.NURTURE,
        ]),
        Prospect.icp_fit_score > 0,
    ]

    if text:
        filters.append(Prospect.full_name.ilike(f"%{text}%"))

    sample_prospects = (
        Prospect.query.filter(*filters)
        .order_by(Prospect.icp_fit_score.desc())
        .offset(offset)
        .limit(limit)
    )
    analytics = [{}]
    if (include_analytics):
        analytics = get_all_campaign_analytics_for_client(
            client_id=ClientArchetype.query.get(client_archetype_id).client_id,
            client_archetype_id=int(client_archetype_id),
        )

    included_individual_title_keywords = []
    included_individual_seniority_keywords = []
    included_individual_locations_keywords = []
    included_individual_industry_keywords = []
    included_individual_generalized_keywords = []
    included_individual_skills_keywords = []
    included_company_name_keywords = []
    included_company_locations_keywords = []
    included_company_generalized_keywords = []
    included_company_industries_keywords = []

    if analytics and len(analytics) > 0:
        included_individual_title_keywords = analytics[0][
            "included_individual_title_keywords"
        ]
        included_individual_seniority_keywords = analytics[0][
            "included_individual_seniority_keywords"
        ]
        included_individual_locations_keywords = analytics[0][
            "included_individual_locations_keywords"
        ]
        included_individual_industry_keywords = analytics[0][
            "included_individual_industry_keywords"
        ]
        included_individual_generalized_keywords = analytics[0][
            "included_individual_generalized_keywords"
        ]
        included_individual_skills_keywords = analytics[0][
            "included_individual_skills_keywords"
        ]
        included_company_name_keywords = analytics[0]["included_company_name_keywords"]
        included_company_locations_keywords = analytics[0][
            "included_company_locations_keywords"
        ]
        included_company_generalized_keywords = analytics[0][
            "included_company_generalized_keywords"
        ]
        included_company_industries_keywords = analytics[0][
            "included_company_industries_keywords"
        ]

    return {
        "included_individual_title_keywords": included_individual_title_keywords,
        "included_individual_locations_keywords": included_individual_locations_keywords,
        "included_individual_seniority_keywords": included_individual_seniority_keywords,
        "included_individual_industry_keywords": included_individual_industry_keywords,
        "included_individual_generalized_keywords": included_individual_generalized_keywords,
        "included_individual_skills_keywords": included_individual_skills_keywords,
        "included_company_name_keywords": included_company_name_keywords,
        "included_company_locations_keywords": included_company_locations_keywords,
        "included_company_generalized_keywords": included_company_generalized_keywords,
        "included_company_industries_keywords": included_company_industries_keywords,
        "sample_contacts": [p.simple_to_dict() for p in sample_prospects],
    }
def fetch_all_assets_in_client(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id: int = client_sdr.client_id

    return ClientAssets.query.filter(
        ClientAssets.client_id == client_id,
    ).all()

def get_client_archetype_sequences(client_archetype_id):
    client_sdr: ClientSDR = ClientSDR.query.get(ClientArchetype.query.get(client_archetype_id).client_sdr_id)

    email_sequence = get_email_sequence_step_for_sdr(
        client_sdr_id=client_sdr.id,
        overall_statuses=[
            ProspectOverallStatus.PROSPECTED,
            ProspectOverallStatus.SENT_OUTREACH,
            ProspectOverallStatus.ACCEPTED,
            ProspectOverallStatus.BUMPED,
        ],
        client_archetype_ids=[client_archetype_id],
        activeOnly=True,
    )

    def sort_func(x):
        bumped_count = x["step"]["bumped_count"]
        overall_status = x["step"]["overall_status"]

        if overall_status == "PROSPECTED":
            return 0
        elif overall_status == "ACCEPTED":
            return 1
        elif overall_status == "BUMPED":
            return bumped_count + 2
        else:
            return 20

    email_sequence = sorted(email_sequence, key=sort_func)

    unique_bump_count_overall_status = set()
    filtered_email_sequence = []
    for step_data in email_sequence:
        bumped_count = step_data["step"]["bumped_count"]
        overall_status = step_data["step"]["overall_status"]
        # if (bumped_count, overall_status) not in unique_bump_count_overall_status:
        #will give every variant
        unique_bump_count_overall_status.add((bumped_count, overall_status))
        filtered_email_sequence.append(step_data)

    email_sequence = [
        {
            "active": step_data["step"]["active"],
            "title": step_data["step"]["title"],
            "description": step_data["step"]["template"],
            "bumped_count": step_data["step"]["bumped_count"],
            "overall_status": step_data["step"]["overall_status"],
            "assets": step_data["assets"],
        }
        for step_data in filtered_email_sequence
    ]

    query = """
        select
            id,
            title,
            description,
            bumped_count,
            active,
            overall_status
        from
            bump_framework
        where client_archetype_id = {client_archetype_id}
            and overall_status in ('ACCEPTED', 'BUMPED')
            and active = true
        order by
            bumped_count asc;
    """.format(
        client_archetype_id=client_archetype_id
    )
    from src.email_sequencing.models import EmailSubjectLineTemplate

    email_subject_lines = EmailSubjectLineTemplate.query.filter(
        EmailSubjectLineTemplate.client_archetype_id == client_archetype_id,
    ).all()

    data = db.session.execute(query).fetchall()
    linkedin_sequence = [
        {
            "bump_framework_id": row[0],
            "title": row[1],
            "description": "Instruction: " + str(row[2]),
            "bumped_count": row[3],
            "assets": get_all_bump_framework_assets(row[0]),
            "active": row[4],
            "overall_status": row[5],
        }
        for row in data
    ]

    initialMessageTemplates: list[LinkedinInitialMessageTemplate] = (
        LinkedinInitialMessageTemplate.query.filter(
            LinkedinInitialMessageTemplate.client_archetype_id == client_archetype_id,
        ).all()
    )

    return {
        "email_subject_lines": [subject.to_dict() for subject in email_subject_lines],
        "email_sequence": email_sequence,
        "linkedin_sequence": linkedin_sequence,
        "initial_message_templates": [template.to_dict() for template in initialMessageTemplates],
    }


def fetch_archetype_assets(client_archetype_id: int):
    assets_query = """
      select
        client_assets.asset_key "title",
        client_assets.asset_value "value",
        client_asset_archetype_reason_mapping.reason "reason",
        client_assets.id "id"
      from client_assets
        left join client_asset_archetype_reason_mapping
          on client_asset_archetype_reason_mapping.client_asset_id = client_assets.id
              and client_asset_archetype_reason_mapping.client_archetype_id = {ARCHETYPE_ID}
      where
        {ARCHETYPE_ID} = any(client_assets.client_archetype_ids);
    """.format(
        ARCHETYPE_ID=client_archetype_id
    )
    assets_data = db.session.execute(assets_query).fetchall()
    return [
        {"title": row[0], "value": row[1], "reason": row[2], "id": row[3]}
        for row in assets_data
    ]


def check_archetype_finished(client_archetype_id: int) -> bool:
    """Checks whether an archetype is finished or not. Archetypes are finished when there are no more eligible prospects available for all activated channels.

    Args:
        client_archetype_id (int): ID of the client archetype

    Returns:
        bool: True if finished, False if not
    """

    def check_linkedin_finished(client_archetype: ClientArchetype) -> bool:
        """Helper function to check if LinkedIn is finished for a given archetype"""
        if not client_archetype.linkedin_active:
            return True

        linkedin_eligible_prospects: list[Prospect] = Prospect.query.filter(
            Prospect.archetype_id == client_archetype.id,
            Prospect.status == ProspectStatus.PROSPECTED,
            Prospect.linkedin_url != None,
        ).all()
        if not linkedin_eligible_prospects:
            return True
        return False

    def check_email_finished(client_archetype: ClientArchetype) -> bool:
        """Helper function to check if Email is finished for a given archetype"""
        if not client_archetype.email_active:
            return True

        email_eligible_prospects: list[Prospect] = Prospect.query.filter(
            Prospect.archetype_id == client_archetype.id,
            Prospect.approved_prospect_email_id == None,
            Prospect.email != None,
        ).all()
        if not email_eligible_prospects:
            return True
        return False

    # Ensure that the archetype exists and is active
    archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not archetype:
        return False
    if not archetype.active:
        return True

    # Only check active if LinkedIn or Email have been active in the past
    linkedin_has_been_active = (
        archetype.meta_data.get("linkedin_has_been_active", True)
        if archetype.meta_data
        else False
    )
    email_has_been_active = (
        archetype.meta_data.get("email_has_been_active", True)
        if archetype.meta_data
        else False
    )

    # Check that the campaign is finished
    linkedin_finished = linkedin_has_been_active
    email_finished = email_has_been_active
    if linkedin_has_been_active:
        linkedin_finished = check_linkedin_finished(archetype)
    if email_has_been_active:
        email_finished = check_email_finished(archetype)

    # Check that the campaign is finished
    finished = linkedin_finished and email_finished
    return finished


@celery.task
def auto_turn_off_finished_archetypes() -> int:
    """Automatically turns off any finished campaigns and sends a Slack Notifications. Will return the number of campaigns that were turned off. Ran by a cron job.

    Returns:
        int: Number of campaigns turned off
    """
    # Get all active archetypes
    active_archetypes: list[ClientArchetype] = ClientArchetype.query.filter_by(
        active=True,
    ).all()

    for archetype in active_archetypes:
        print(f"Checking {archetype.archetype} #{archetype.id}")
        # Check if the archetype is finished
        if check_archetype_finished(archetype.id):
            print(f"Turning off {archetype.archetype} #{archetype.id}")
            # Send a Slack Notification
            sdr: ClientSDR = ClientSDR.query.get(archetype.client_sdr_id)
            success = create_and_send_slack_notification_class_message(
                notification_type=SlackNotificationType.CAMPAIGN_COMPLETED,
                arguments={
                    "client_sdr_id": sdr.id,
                    "campaign_id": archetype.id,
                },
            )

            # Turn off the archetype
            deactivate_client_archetype(archetype.client_sdr_id, archetype.id, True, False)

def set_email_to_linkedin_connection(
    client_sdr_id: int,
    client_archetype_id: int,
    connection_type: EmailToLinkedInConnection,
):
    """
    Set the email to linkedin connection type for a given archetype
    """
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not client_archetype:
        return False
    if client_archetype.client_sdr_id != client_sdr_id:
        return False
    
    client_archetype.email_to_linkedin_connection = connection_type
    db.session.add(client_archetype)
    db.session.commit()

    return True

def get_email_to_linkedin_connection_amounts(
    client_sdr_id: int,
    client_archetype_id: int,
):
    """
    Get the amount of email to linkedin connections for a given archetype
    """
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not client_archetype:
        return False
    if client_archetype.client_sdr_id != client_sdr_id:
        return False

    query= """
        select 
            count(distinct prospect.id) filter (where prospect_email_status_records.to_status = 'SENT_OUTREACH') "prospects_sent_outreach",
            count(distinct prospect.id) filter (where prospect_email_status_records.to_status = 'EMAIL_OPENED') "prospects_email_opened",
            count(distinct prospect.id) filter (where prospect_email_status_records.to_status = 'ACCEPTED') "prospects_clicked"
        from prospect
            left join prospect_email on prospect_email.id = prospect.approved_prospect_email_id
            left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
        where archetype_id = {client_archetype_id}
            and prospect.overall_status in ('SENT_OUTREACH', 'PROSPECTED', 'BUMPED', 'ACCEPTED');
    """.format(client_archetype_id=client_archetype_id)

    data = db.session.execute(query).fetchone()

    return {
        "prospects_sent_outreach": data[0],
        "prospects_email_opened": data[1],
        "prospects_clicked": data[2],
    }

def set_personalizers_enabled(
    client_sdr_id: int,
    client_archetype_id: int,
    personalizers_enabled: bool,
):
    """
    Set the personalizers enabled for a given archetype
    """
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not client_archetype:
        return False
    if client_archetype.client_sdr_id != client_sdr_id:
        return False

    client_archetype.is_ai_research_personalization_enabled = personalizers_enabled
    db.session.add(client_archetype)
    db.session.commit()

    return True
