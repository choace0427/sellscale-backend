import datetime
from typing import List, Optional, Tuple

from src.utils.lists import chunk_list

from src.prospecting.services import update_prospect_status_email

from src.email_outbound.models import (
    ProspectEmail,
    ProspectEmailOutreachStatus,
    ProspectEmailStatus,
)
from src.prospecting.models import Prospect

from src.utils.slack import send_slack_message, URL_MAP

from src.client.models import ClientArchetype, ClientSDR
from src.smartlead.smartlead import (
    Lead,
    Smartlead,
    EmailWarming,
    SmartleadCampaignStatisticEntry,
)

from app import db, celery


def get_all_email_warmings(sdr_name: str) -> list[EmailWarming]:
    sl = Smartlead()
    emails = sl.get_emails()

    warmings = []
    for email in emails:
        if sdr_name != email.get("from_name"):
            continue

        warmup_stats = sl.get_warmup_stats(email.get("id"))
        warming = EmailWarming(
            id=email.get("id"),
            name=email.get("from_name"),
            email=email.get("from_email"),
            status=email.get("warmup_details", {}).get("status"),
            total_sent=email.get("warmup_details", {}).get("total_sent_count"),
            total_spam=email.get("warmup_details", {}).get("total_spam_count"),
            warmup_reputation=email.get("warmup_details", {}).get("warmup_reputation"),
            sent_count=warmup_stats.get("sent_count"),
            spam_count=warmup_stats.get("spam_count"),
            inbox_count=warmup_stats.get("inbox_count"),
            warmup_email_received_count=warmup_stats.get("warmup_email_received_count"),
            stats_by_date=warmup_stats.get("stats_by_date"),
            percent_complete=get_warmup_percentage(int(warmup_stats.get("sent_count"))),
        )
        warmings.append(warming)

    return warmings


@celery.task
def sync_email_warmings(client_sdr_id: int, email: str):
    from src.warmup_snapshot.models import WarmupSnapshot

    return True, "Success"

    warmings = get_email_warmings_for_sdr(client_sdr_id)
    snapshot: WarmupSnapshot = WarmupSnapshot.query.filter_by(
        account_name=email
    ).first()

    snapshot.warming_details = [warming.to_dict() for warming in warmings]
    db.session.commit()

    return True, "Success"


def get_email_warmings_for_sdr(client_sdr_id: int) -> list[EmailWarming]:
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if sdr.meta_data:
        old_warmings = sdr.meta_data.get("email_warmings", [])
    else:
        old_warmings = []

    warmings: list[EmailWarming] = get_all_email_warmings(sdr.name)
    for warming in warmings:
        for old_warming in old_warmings:
            if warming.id == old_warming.get("id"):
                # Finished warming
                if (
                    warming.percent_complete == 100
                    and old_warming.get("percent_complete") != 100
                ):
                    send_slack_message(
                        message="🔥 Domain warmed",
                        blocks=[
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"🔥 *Domain warmed -* `{warming.email}`,",
                                },
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f">_A SellScale AI domain has finished warming. It may now be used to send up to 40 emails/day._",
                                },
                            },
                        ],
                        webhook_urls=[URL_MAP["ops-outbound-warming"]],
                    )

    if sdr.meta_data:
        sdr.meta_data["email_warmings"] = [warming.to_dict() for warming in warmings]
    else:
        sdr.meta_data = {"email_warmings": [warming.to_dict() for warming in warmings]}
    db.session.commit()

    return warmings


def get_warmup_percentage(sent_count: int) -> int:
    TOTAL_SENT = 160

    return min(round((sent_count / TOTAL_SENT) * 100, 0), 100)


# def get_warmup_percentage(warming_stats_by_date: list) -> int:
#     WARMUP_LENGTH = 14

#     first = warming_stats_by_date[0]
#     # last = warming_stats_by_date[-1]

#     # Convert date strings to datetime objects
#     date_first = datetime.datetime.strptime(first.get('date'), '%Y-%m-%d')
#     date_last = datetime.datetime.utcnow() #.strptime(last.get('date'), '%Y-%m-%d')

#     # Calculate the difference between the two dates
#     date_difference = date_last - date_first

#     return min(round((date_difference.days / WARMUP_LENGTH) * 100, 0), 100)


def sync_campaign_analytics(client_sdr_id: int) -> bool:
    archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
    ).all()

    for archetype in archetypes:
        if archetype.smartlead_campaign_id == None:
            continue

        # if archetype.meta_data:
        #     analytics = archetype.meta_data.get("smartlead_campaign_analytics", {})
        # else:
        #     analytics = {}

        sl = Smartlead()
        analytics = sl.get_campaign_analytics(archetype.smartlead_campaign_id)

        if archetype.meta_data:
            archetype.meta_data["smartlead_campaign_analytics"] = analytics
        else:
            archetype.meta_data = {"smartlead_campaign_analytics": analytics}
        db.session.commit()


def set_campaign_id(archetype_id: int, campaign_id: int) -> bool:
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    archetype.smartlead_campaign_id = campaign_id
    db.session.commit()

    return True


def sync_campaign_leads(client_sdr_id: int) -> bool:
    archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
    ).all()

    for archetype in archetypes:
        if archetype.smartlead_campaign_id == None:
            continue

        sl = Smartlead()
        statistics = sl.get_campaign_statistics_by_id(archetype.smartlead_campaign_id)
        statistics = statistics.get("data")
        if not statistics:
            raise Exception("No smartlead campaign statistics found")

        from src.automation.orchestrator import add_process_list, add_process_to_queue

        for lead in statistics:
            args = {
                "client_id": archetype.client_id,
                "archetype_id": archetype.id,
                "client_sdr_id": client_sdr_id,
                "lead": lead,
            }
            add_process_to_queue(
                type="sync_prospect_with_lead",
                meta_data={"args": args},
                execution_date=datetime.datetime.utcnow(),
                commit=True,
            )

        # add_process_list(
        #     type="sync_prospect_with_lead",
        #     args_list=[
        #         {
        #             "client_id": archetype.client_id,
        #             "archetype_id": archetype.id,
        #             "client_sdr_id": client_sdr_id,
        #             "lead": lead,
        #         }
        #         for lead in leads
        #     ],
        #     buffer_wait_minutes=1,
        # )


@celery.task
def sync_prospect_with_lead(
    client_id: int, archetype_id: int, client_sdr_id: int, lead: dict
):
    # 0. Turn the lead into a SmartleadCampaignStatisticEntry object
    lead: SmartleadCampaignStatisticEntry = SmartleadCampaignStatisticEntry(**lead)

    # 1. Try to find the prospect by email. If not found, return False
    prospect: Prospect = Prospect.query.filter(
        Prospect.email == lead.lead_email,
        Prospect.client_sdr_id == client_sdr_id,
    ).first()
    if not prospect:
        return False, "Prospect not found"

    # 2. Get the corresponding prospect email. If not found, create a new one
    prospect_email_id = prospect.approved_prospect_email_id
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    if not prospect_email:
        # Create a new prospect email
        prospect_email: ProspectEmail = ProspectEmail(
            prospect_id=prospect.id,
            email_status=ProspectEmailStatus.APPROVED,
            outreach_status=ProspectEmailOutreachStatus.NOT_SENT,
        )
        db.session.add(prospect_email)
        db.session.commit()

        prospect.approved_prospect_email_id = prospect_email.id
        prospect_email_id = prospect_email.id
        db.session.commit()
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)

    # 3a. If the lead was sent an email and had previously not, update the prospect email status
    if (
        lead.sent_time
        and prospect_email.outreach_status == ProspectEmailOutreachStatus.NOT_SENT
    ):
        print('Updating prospect email status to "SENT_OUTREACH"')
        update_prospect_status_email(
            prospect_id=prospect.id,
            new_status=ProspectEmailOutreachStatus.SENT_OUTREACH,
            quietly=True,
        )

    # 3b. If the lead has opened the email and had previously not, update the prospect email status
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    if (
        lead.open_time
        and prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
    ):
        print('Updating prospect email status to "EMAIL_OPENED"')
        update_prospect_status_email(
            prospect_id=prospect.id,
            new_status=ProspectEmailOutreachStatus.EMAIL_OPENED,
            quietly=True,
        )

    # 3c. If the lead has replied to the email and had previously not, update the prospect email status
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    if lead.reply_time and (
        prospect_email.outreach_status == ProspectEmailOutreachStatus.EMAIL_OPENED
        or prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
    ):
        print('Updating prospect email status to "ACTIVE_CONVO"')
        if prospect_email.outreach_status == ProspectEmailOutreachStatus.EMAIL_OPENED:
            update_prospect_status_email(
                prospect_id=prospect.id,
                new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                quietly=True,
            )
        elif (
            prospect_email.outreach_status == ProspectEmailOutreachStatus.SENT_OUTREACH
        ):
            # TODO: One day, we may use smartlead's behavior with OOOs having a reply_time but no open_time to create OOO special behavior
            # For now, we'll just mark it as EMAIL_OPENED, and then ACTIVE_CONVO
            update_prospect_status_email(
                prospect_id=prospect.id,
                new_status=ProspectEmailOutreachStatus.EMAIL_OPENED,
                quietly=True,
            )
            update_prospect_status_email(
                prospect_id=prospect.id,
                new_status=ProspectEmailOutreachStatus.ACTIVE_CONVO,
                quietly=True,
            )

    return True, "Success"


def sync_prospects_to_campaign(client_sdr_id: int, archetype_id: int):
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if archetype.smartlead_campaign_id == None:
        return

    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.archetype_id == archetype_id
    ).all()

    sl = Smartlead()

    leads = sl.get_leads_export(archetype.smartlead_campaign_id)
    # Filter out all prospects that are already in the campaign
    prospects = [
        prospect
        for prospect in prospects
        if prospect.email not in [lead.get("email") for lead in leads]
    ]

    prospect_chunks = chunk_list(
        prospects, 100
    )  # max 100 leads can be added at a time with API
    for chunk in prospect_chunks:
        result = sl.add_campaign_leads(
            campaign_id=archetype.smartlead_campaign_id,
            leads=[
                Lead(
                    first_name=prospect.first_name,
                    last_name=prospect.last_name,
                    email=prospect.email,
                    phone_number=None,
                    company_name=prospect.company,
                    website=None,
                    location=None,
                    custom_fields={"source": "SellScale"},
                    linkedin_profile=prospect.linkedin_url,
                    company_url=prospect.company_url,
                )
                for prospect in chunk
            ],
        )
        # print(result)

    send_slack_message(
        message=f"Imported {len(prospects)} prospects to Smartlead campaign from {archetype.archetype} (#{archetype.id})",
        webhook_urls=[URL_MAP["ops-outbound-warming"]],
    )

    return True, len(prospects)
