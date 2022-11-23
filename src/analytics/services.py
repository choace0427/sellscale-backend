from src.client.models import *
from datetime import datetime, timedelta
from src.message_generation.models import *
from app import db
from src.prospecting.models import *


def get_all_latest_week_benchmarks_for_clients():
    clients: list = Client.query.filter(Client.active == True, Client.id != 1).all()

    latest_benchmarks = []
    for client in clients:
        print(client, client.company)
        benchmarks = get_li_message_benchmarks_for_client(client.id)
        if len(benchmarks) > 0:
            latest_benchmarks.append(benchmarks[-1])

    return latest_benchmarks


def get_weekly_client_sdr_outbound_goal_map():
    results = db.session.execute(
        """
        select client_sdr.client_id, sum(client_sdr.weekly_li_outbound_target) from client_sdr group by 1;
    """
    ).fetchall()

    outbound_goal_map = {}
    for res in results:
        outbound_goal_map[res[0]] = res[1]

    return outbound_goal_map


def get_li_message_benchmarks_for_client(client_id: int):
    updates = []

    client: Client = Client.query.get(client_id)
    idx = (client.created_at.weekday() + 1) % 7
    created_at = client.created_at - timedelta(7 + idx - 6)
    now_time = datetime.now()

    days_between = (now_time - created_at).days

    for i in range(0, days_between + 7, 7):
        interval_start = created_at + timedelta(days=i - 7)
        interval_end = created_at + timedelta(days=i)

        unique_prospects_generated_count: GeneratedMessage = (
            db.session.query(GeneratedMessage, Prospect)
            .filter(
                GeneratedMessage.prospect_id == Prospect.id,
                GeneratedMessage.created_at >= interval_start,
                GeneratedMessage.created_at < interval_end,
                Prospect.client_id == client.id,
                Prospect.status != ProspectStatus.NOT_QUALIFIED,
            )
            .distinct(GeneratedMessage.prospect_id)
            .count()
        )

        unique_prospects_edited: GeneratedMessage = (
            db.session.query(GeneratedMessage, Prospect)
            .filter(
                GeneratedMessage.prospect_id == Prospect.id,
                GeneratedMessage.created_at >= interval_start,
                GeneratedMessage.created_at < interval_end,
                Prospect.approved_outreach_message_id != None,
                Prospect.client_id == client.id,
                Prospect.status != ProspectStatus.NOT_QUALIFIED,
            )
            .distinct(GeneratedMessage.prospect_id)
            .count()
        )

        unique_prospects_sent_count: GeneratedMessage = (
            db.session.query(GeneratedMessage, Prospect)
            .filter(
                GeneratedMessage.prospect_id == Prospect.id,
                GeneratedMessage.created_at >= interval_start,
                GeneratedMessage.message_status == GeneratedMessageStatus.SENT,
                GeneratedMessage.created_at < interval_end,
                Prospect.client_id == client.id,
            )
            .distinct(GeneratedMessage.prospect_id)
            .count()
        )

        prospect_status_to_accepted = (
            db.session.query(Prospect, GeneratedMessage)
            .filter(
                Prospect.client_id == client.id,
                Prospect.id == ProspectStatusRecords.prospect_id,
                GeneratedMessage.prospect_id == Prospect.id,
                Prospect.status == ProspectStatus.ACCEPTED,
                GeneratedMessage.created_at >= interval_start,
                GeneratedMessage.created_at < interval_end,
            )
            .distinct(ProspectStatusRecords.prospect_id)
            .count()
        )

        prospect_status_to_responded = (
            db.session.query(Prospect, GeneratedMessage)
            .filter(
                Prospect.client_id == client.id,
                Prospect.id == ProspectStatusRecords.prospect_id,
                GeneratedMessage.prospect_id == Prospect.id,
                Prospect.status.in_(
                    [ProspectStatus.RESPONDED, ProspectStatus.NOT_INTERESTED]
                ),
                GeneratedMessage.created_at >= interval_start,
                GeneratedMessage.created_at < interval_end,
            )
            .distinct(ProspectStatusRecords.prospect_id)
            .count()
        )

        prospect_status_to_active_convo = (
            db.session.query(Prospect, GeneratedMessage)
            .filter(
                Prospect.client_id == client.id,
                Prospect.id == ProspectStatusRecords.prospect_id,
                Prospect.status == ProspectStatus.ACTIVE_CONVO,
                GeneratedMessage.prospect_id == Prospect.id,
                GeneratedMessage.created_at >= interval_start,
                GeneratedMessage.created_at < interval_end,
            )
            .distinct(ProspectStatusRecords.prospect_id)
            .count()
        )

        prospect_status_to_scheduling = (
            db.session.query(Prospect, GeneratedMessage)
            .filter(
                Prospect.client_id == client.id,
                Prospect.id == ProspectStatusRecords.prospect_id,
                Prospect.status == ProspectStatus.SCHEDULING,
                GeneratedMessage.prospect_id == Prospect.id,
                GeneratedMessage.created_at >= interval_start,
                GeneratedMessage.created_at < interval_end,
            )
            .distinct(ProspectStatusRecords.prospect_id)
            .count()
        )

        prospect_status_to_demo_set = (
            db.session.query(Prospect, GeneratedMessage)
            .filter(
                Prospect.client_id == client.id,
                Prospect.id == ProspectStatusRecords.prospect_id,
                Prospect.status.in_(
                    [
                        ProspectStatus.DEMO_SET,
                        ProspectStatus.DEMO_LOSS,
                        ProspectStatus.DEMO_WON,
                    ]
                ),
                GeneratedMessage.prospect_id == Prospect.id,
                GeneratedMessage.created_at >= interval_start,
                GeneratedMessage.created_at < interval_end,
            )
            .distinct(ProspectStatusRecords.prospect_id)
            .count()
        )

        weekly_targets = get_weekly_client_sdr_outbound_goal_map()

        updates.append(
            {
                "client_name": client.company,
                "client_id": client.id,
                "interval_start": interval_start,
                "interval_end": interval_end,
                "weekly_target": weekly_targets.get(client.id, -1),
                "generated": unique_prospects_generated_count,
                "edited": unique_prospects_edited,
                "sent": unique_prospects_sent_count,
                "accepted": prospect_status_to_accepted,
                "responded": prospect_status_to_responded,
                "active_convo": prospect_status_to_active_convo,
                "scheduling": prospect_status_to_scheduling,
                "demo_set": prospect_status_to_demo_set,
            }
        )

    return updates
