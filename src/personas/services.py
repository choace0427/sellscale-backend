from model_import import (
    PersonaSplitRequest,
    PersonaSplitRequestTask,
    PersonaSplitRequestTaskStatus,
    ClientArchetype,
    Prospect,
)
from app import db


def verify_client_sdr_can_access_archetype(client_sdr_id: int, archetype_id: int):
    ca: ClientArchetype = ClientArchetype.query.filter_by(id=archetype_id).first()
    if ca is None:
        return False, "Archetype not found"
    if ca.client_sdr_id != client_sdr_id:
        return False, "Client SDR does not have access to this archetype"
    return True, "OK"


def create_persona_split_request(
    client_sdr_id: int,
    source_archetype_id: int,
    destination_archetype_ids: list[int],
) -> tuple[bool, str]:
    """
    Given a client SDR, source archetype, and destination archetypes, create a persona split request and tasks
    """
    # check if client sdr has access to archetypes
    all_archetypes = [source_archetype_id] + destination_archetype_ids
    for archetype_id in all_archetypes:
        ok, msg = verify_client_sdr_can_access_archetype(client_sdr_id, archetype_id)
        if not ok:
            return False, msg

    persona_split_request = PersonaSplitRequest(
        client_sdr_id=client_sdr_id,
        source_client_archetype_id=source_archetype_id,
        destination_client_archetype_ids=destination_archetype_ids,
    )
    db.session.add(persona_split_request)
    db.session.commit()
    persona_split_request_id = persona_split_request.id

    # create tasks
    prospects: list[Prospect] = Prospect.query.filter_by(
        archetype_id=source_archetype_id
    ).all()
    tasks = []
    for prospect in prospects:
        task = PersonaSplitRequestTask(
            persona_split_request_id=persona_split_request_id,
            prospect_id=prospect.id,
            destination_client_archetype_ids=destination_archetype_ids,
            status=PersonaSplitRequestTaskStatus.QUEUED,
        )
        tasks.append(task)
    db.session.bulk_save_objects(tasks)
    db.session.commit()

    return True, "OK"


def get_recent_split_requests(client_sdr_id: int, source_archetype_id: int):
    """
    Given a client sdr id, return a list of recent split requests
    """
    split_requests: list[PersonaSplitRequest] = (
        PersonaSplitRequest.query.filter_by(
            client_sdr_id=client_sdr_id, source_client_archetype_id=source_archetype_id
        )
        .order_by(PersonaSplitRequest.created_at.desc())
        .all()
    )
    return [sr.to_dict() for sr in split_requests]


def get_split_request_details(split_request_id: int):
    """
    Given a split request id, return the split request details

    Will find all SplitRequestTasks associated with the SplitRequest and return the details

    Details look like:
    {
        total_tasks: int,
        breakdown: {
            queued: int,
            in_progress: int,
            completed: int,
            failed: int,
        },
        split_request_id: int,
        source_archetype_id: int,
        destination_archetype_ids: list[int],
        source_archetype_name: str,
        destination_archetype_names: list[str],
    }
    """
    split_request: PersonaSplitRequest = PersonaSplitRequest.query.filter_by(
        id=split_request_id
    ).first()
    if split_request is None:
        return None
    tasks: list[PersonaSplitRequestTask] = PersonaSplitRequestTask.query.filter_by(
        persona_split_request_id=split_request_id
    ).all()
    source_archetype: ClientArchetype = ClientArchetype.query.filter_by(
        id=split_request.source_client_archetype_id
    ).first()
    destination_archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.id.in_(split_request.destination_client_archetype_ids)
    ).all()
    total_tasks = len(tasks)
    breakdown = {
        PersonaSplitRequestTaskStatus.QUEUED: 0,
        PersonaSplitRequestTaskStatus.IN_PROGRESS: 0,
        PersonaSplitRequestTaskStatus.COMPLETED: 0,
        PersonaSplitRequestTaskStatus.FAILED: 0,
    }
    for task in tasks:
        breakdown[task.status] += 1
    return {
        "total_tasks": total_tasks,
        "breakdown": {
            "queued": breakdown[PersonaSplitRequestTaskStatus.QUEUED],
            "in_progress": breakdown[PersonaSplitRequestTaskStatus.IN_PROGRESS],
            "completed": breakdown[PersonaSplitRequestTaskStatus.COMPLETED],
            "failed": breakdown[PersonaSplitRequestTaskStatus.FAILED],
        },
        "split_request_id": split_request.id,
        "source_archetype_id": source_archetype.id,
        "destination_archetype_ids": [ca.id for ca in destination_archetypes],
        "source_archetype_name": source_archetype.archetype,
        "destination_archetype_names": [ca.archetype for ca in destination_archetypes],
    }
