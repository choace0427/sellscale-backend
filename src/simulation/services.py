import datetime
from typing import List, Optional, Tuple

from app import db, celery
from src.client.models import ClientArchetype
from src.li_conversation.models import LinkedInConvoMessage
from src.prospecting.models import Prospect
from src.research.linkedin.services import get_research_and_bullet_points_new
from src.simulation.models import (
    Simulation,
    SimulationType,
    SimulationRecord,
    SimulationRecordType,
)


def create_simulation(
    client_sdr_id: int, archetype_id: int, prospect_id: int, type: SimulationType
):
    simulation = Simulation(
        client_sdr_id=client_sdr_id,
        archetype_id=archetype_id,
        prospect_id=prospect_id,
        type=type,
    )
    db.session.add(simulation)
    db.session.commit()

    return simulation.id


def send_li_convo_message(
    simulation_id: int,
    message: LinkedInConvoMessage,
    meta_data: Optional[dict] = None,
    message_date: Optional[datetime.datetime] = None,
):
    simulation: Simulation = Simulation.query.get(simulation_id)
    if not simulation:
        return False

    max_simulation_record_created_date = (
        SimulationRecord.query.filter(SimulationRecord.simulation_id == simulation_id)
        .order_by(SimulationRecord.created_at.desc())
        .first()
    )

    record = SimulationRecord(
        simulation_id=simulation_id,
        client_sdr_id=simulation.client_sdr_id,
        archetype_id=simulation.archetype_id,
        prospect_id=simulation.prospect_id,
        type=SimulationRecordType.LI_CONVERSATION_MESSAGE,
        data={
            "author": message.author,
            "message": message.message,
            "connection_degree": message.connection_degree,
            "li_id": message.li_id,
        },
        meta_data=meta_data or message.meta_data or None,
    )
    if message_date:
        record.created_at = message_date
    elif max_simulation_record_created_date:
        record.created_at = (
            max_simulation_record_created_date.created_at + datetime.timedelta(hours=1)
        )
    db.session.add(record)
    db.session.commit()

    return True


def get_sim_li_convo_history(
    simulation_id: int, fetchAll: bool = False, inverted_order=False
) -> List[LinkedInConvoMessage]:
    """
    Fetches the last 5 messages of a simulation's conversation
    """

    query = SimulationRecord.query.filter(
        SimulationRecord.simulation_id == simulation_id,
        SimulationRecord.type == SimulationRecordType.LI_CONVERSATION_MESSAGE,
    ).order_by(SimulationRecord.created_at.desc())
    if not fetchAll:
        query = query.limit(5)

    simulation_msgs: List[SimulationRecord] = query.all()

    retval = [
        LinkedInConvoMessage(
            message=sim_msg.data.get("message", ""),
            connection_degree=sim_msg.data.get("connection_degree", "You"),
            author=sim_msg.data.get("author", ""),
            li_id=sim_msg.data.get("li_id", None),
            meta_data=sim_msg.meta_data,
            date=sim_msg.created_at,
        )
        for sim_msg in simulation_msgs
    ]

    if inverted_order:
        retval = retval[::-1]

    return retval


def generate_sim_li_convo_init_msg(
    simulation_id: int, template_id: Optional[int] = None
):
    """Generates the initial message for a simulated linkedin conversation

    Args:
        simulation_id (int): The simulation id

    Returns:
        bool: Whether or not a message was generated
    """

    from src.client.models import ClientSDR
    from src.message_generation.services import generate_li_convo_init_msg

    simulation: Simulation = Simulation.query.get(simulation_id)
    if not simulation:
        return False
    if simulation.type != SimulationType.LI_CONVERSATION:
        return False

    message, meta_data = generate_li_convo_init_msg(simulation.prospect_id, template_id)

    client_sdr: ClientSDR = ClientSDR.query.get(simulation.client_sdr_id)

    success = send_li_convo_message(
        simulation_id=simulation_id,
        message=LinkedInConvoMessage(
            message=message,
            connection_degree="You",
            author=client_sdr.name,
        ),
        meta_data=meta_data,
    )
    return success


def generate_sim_li_convo_response(simulation_id: int) -> Tuple[bool, str]:
    """Updates the simulation and generates a response to the current conversation state

    Args:
        simulation_id (int): The simulation id

    Returns:
        bool: Whether or not the simulation was updated and a response was generated
    """

    from src.message_generation.services import generate_followup_response
    from src.prospecting.models import ProspectOverallStatus, ProspectStatus
    from src.client.models import ClientSDR, Prospect, ClientArchetype

    simulation: Simulation = Simulation.query.get(simulation_id)
    if not simulation:
        return False, "No simulation found."
    if simulation.type != SimulationType.LI_CONVERSATION:
        return False, "Wrong simulation type."
    if simulation.meta_data is None:
        return False, "Missing meta data."

    convo_history = get_sim_li_convo_history(simulation_id, inverted_order=True)
    if len(convo_history) == 0:
        return False, "No conversation history."

    overall_status = simulation.meta_data.get("overall_status", None)
    li_status = simulation.meta_data.get("li_status", None)
    bump_count = simulation.meta_data.get("bump_count", None)

    if overall_status is None or li_status is None or bump_count is None:
        return False, "Missing meta data."

    # If we've already hit our max bump count, skip
    prospect: Prospect = Prospect.query.get(simulation.prospect_id)
    client_archetype: ClientArchetype = ClientArchetype.query.get(prospect.archetype_id)
    if (
        prospect.times_bumped
        and client_archetype.li_bump_amount <= prospect.times_bumped
    ):
        return False, "Prospect has been bumped too many times."

    try:
        data = generate_followup_response(
            client_sdr_id=simulation.client_sdr_id,
            prospect_id=simulation.prospect_id,
            overall_status=ProspectOverallStatus[overall_status],
            li_status=ProspectStatus[li_status],
            bump_count=bump_count,
            convo_history=convo_history,
            show_slack_messages=False,
        )

        if data is None:
            return False, "No bump framework found."

        client_sdr: ClientSDR = ClientSDR.query.get(simulation.client_sdr_id)

        max_simulation_record_date = max(
            [msg.date for msg in convo_history if msg.date is not None]
        )

        success = send_li_convo_message(
            simulation_id=simulation_id,
            message=LinkedInConvoMessage(
                message=data.get("response", ""),
                connection_degree="You",
                author=client_sdr.name,
            ),
            message_date=max_simulation_record_date
            + datetime.timedelta(days=data.get("bump_framework_delay", 2) or 2),
            meta_data={
                "prompt": data.get("prompt", ""),
                "bump_framework_id": data.get("bump_framework_id", None),
                "bump_framework_title": data.get("bump_framework_title", None),
                "bump_framework_description": data.get(
                    "bump_framework_description", None
                ),
                "bump_framework_length": data.get("bump_framework_length", None),
                "account_research_points": data.get("account_research_points", None),
                "bump_framework_delay": data.get("bump_framework_delay", None),
            },
        )

        return success, "Response"

    except Exception as e:
        print(e)
        return False, str(e)


def update_sim_li_convo(simulation_id: int):
    """Updates the simulation metadata to reflect the current state of the conversation

    Args:
        simulation_id (int): The simulation to update

    Returns:
        bool: Whether or not the simulation was updated
    """

    from src.prospecting.models import ProspectStatus
    from src.voyager.services import get_prospect_status_from_convo

    simulation: Simulation = Simulation.query.get(simulation_id)
    if not simulation:
        return False
    if simulation.type != SimulationType.LI_CONVERSATION:
        return False

    convo_history = get_sim_li_convo_history(simulation_id)

    first_and_only_message_was_you = (
        len(convo_history) == 1 and convo_history[0].connection_degree == "You"
    )

    if not simulation.meta_data or first_and_only_message_was_you:
        simulation: Simulation = Simulation.query.get(simulation_id)
        simulation.meta_data = {
            "overall_status": "ACCEPTED",
            "li_status": "ACCEPTED",
            "bump_count": 0,
        }
        db.session.commit()
        print("1")
        return True

    last_msg_was_you = (
        len(convo_history) > 1 and convo_history[0].connection_degree == "You"
    )
    last_2_msg_was_you = (
        len(convo_history) > 2
        and last_msg_was_you
        and convo_history[1].connection_degree == "You"
    )
    last_3_msg_was_you = (
        len(convo_history) > 3
        and last_2_msg_was_you
        and convo_history[2].connection_degree == "You"
    )
    has_prospect_replied = (
        next(filter(lambda x: x.connection_degree != "You", convo_history), None)
        is not None
    )

    # Set to bumped if we send them a followup and they haven't replied
    if (
        simulation.meta_data.get("li_status") in ("SENT_OUTREACH", "ACCEPTED")
        and not has_prospect_replied
        and last_msg_was_you
    ):
        simulation: Simulation = Simulation.query.get(simulation_id)
        simulation.meta_data = {
            "overall_status": "BUMPED",
            "li_status": "RESPONDED",
            "bump_count": 1,
        }
        db.session.commit()
        print("2")
        return True

    # Update the prospect status accordingly
    if (
        first_and_only_message_was_you
        and simulation.meta_data.get("li_status") == "SENT_OUTREACH"
    ):
        simulation: Simulation = Simulation.query.get(simulation_id)
        simulation.meta_data = {
            "overall_status": "ACCEPTED",
            "li_status": "ACCEPTED",
            "bump_count": 0,
        }
        db.session.commit()
        print("3")
        return True

    elif (
        simulation.meta_data.get("li_status")
        in (
            "SENT_OUTREACH",
            "ACCEPTED",
            "RESPONDED",
        )
        and has_prospect_replied
    ) or (
        simulation.meta_data.get("li_status") in ["NOT_INTERESTED"]
        and not last_msg_was_you
    ):
        simulation: Simulation = Simulation.query.get(simulation_id)
        simulation.meta_data = {
            "overall_status": "ACTIVE_CONVO",
            "li_status": "ACTIVE_CONVO",
            "bump_count": 0,
        }
        db.session.commit()
        print("4, continuing...")

    # Set the bumped status and bumped count
    if last_3_msg_was_you and simulation.meta_data.get("li_status") in (
        "ACCEPTED",
        "RESPONDED",
    ):
        simulation: Simulation = Simulation.query.get(simulation_id)
        simulation.meta_data = {
            "overall_status": "BUMPED",
            "li_status": "RESPONDED",
            "bump_count": 3,
        }
        db.session.commit()
        print("5")
        return True

    if last_2_msg_was_you and simulation.meta_data.get("li_status") in (
        "ACCEPTED",
        "RESPONDED",
    ):
        simulation: Simulation = Simulation.query.get(simulation_id)
        simulation.meta_data = {
            "overall_status": "BUMPED",
            "li_status": "RESPONDED",
            "bump_count": 2,
        }
        db.session.commit()
        print("6")
        return True

    if last_msg_was_you and simulation.meta_data.get("li_status") in (
        "ACCEPTED",
        "RESPONDED",
    ):
        simulation: Simulation = Simulation.query.get(simulation_id)
        simulation.meta_data = {
            "overall_status": "BUMPED",
            "li_status": "RESPONDED",
            "bump_count": 1,
        }
        db.session.commit()
        print("7")
        return True

    # Set active convo substatus
    if simulation.meta_data.get("overall_status") == "ACTIVE_CONVO":
        messages = []
        for msg in convo_history:
            timestamp = msg.date.strftime("%m/%d/%Y, %H:%M:%S") if msg.date else ""
            messages.append(f"{msg.author} ({timestamp}): {msg.message}")
            prospect = Prospect.query.get(simulation.prospect_id)
        li_status = get_prospect_status_from_convo(messages, simulation.client_sdr_id, current_status=prospect.status)

        simulation: Simulation = Simulation.query.get(simulation_id)
        simulation.meta_data = {
            "overall_status": "ACTIVE_CONVO",
            "li_status": li_status.value,
            "bump_count": 0,
        }
        db.session.commit()
        print("8")
        return True

    return False


def generate_entire_simulated_conversation(
    archetype_id: int,
) -> Tuple[bool, List[SimulationRecord]]:
    try:
        client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
        num_steps = client_archetype.li_bump_amount + 1
        random_prospect: Prospect = (
            Prospect.query.filter(Prospect.archetype_id == archetype_id)
            .order_by(Prospect.icp_fit_score.desc())
            .first()
        )
        if not random_prospect:
            return False, []

        simulation_id = create_simulation(
            client_sdr_id=client_archetype.client_sdr_id,
            archetype_id=archetype_id,
            prospect_id=random_prospect.id,
            type=SimulationType.LI_CONVERSATION,
        )

        for i in range(num_steps):
            print("Generating step #", i, "...")
            if i == 0:
                generate_sim_li_convo_init_msg(simulation_id)
            else:
                generate_sim_li_convo_response(simulation_id)
            update_sim_li_convo(simulation_id)

        simulation_records: list[SimulationRecord] = (
            SimulationRecord.query.filter(
                SimulationRecord.simulation_id == simulation_id
            )
            .order_by(SimulationRecord.created_at.asc())
            .all()
        )
        return True, simulation_records
    except Exception as e:
        print(e)
        return False, []
