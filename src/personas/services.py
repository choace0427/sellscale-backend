from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from model_import import (
    PersonaSplitRequest,
    PersonaSplitRequestTask,
    PersonaSplitRequestTaskStatus,
    ClientArchetype,
    Prospect,
)
from src.prospecting.services import get_prospect_details
from app import db, celery
import json


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

    tasks = PersonaSplitRequestTask.query.filter_by(
        persona_split_request_id=persona_split_request_id
    ).all()
    for task in tasks:
        process_persona_split_request_task.delay(task.id)

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


@celery.task(bind=True, max_retries=3)
def process_persona_split_request_task(self, task_id: int):
    """
    Given a task id, process the task
    """

    try:
        task: PersonaSplitRequestTask = PersonaSplitRequestTask.query.filter_by(
            id=task_id
        ).first()
        if task is None:
            return
        if task.status in [
            PersonaSplitRequestTaskStatus.COMPLETED,
            PersonaSplitRequestTaskStatus.FAILED,
        ]:
            return

        task.status = PersonaSplitRequestTaskStatus.IN_PROGRESS
        task.tries += 1
        db.session.add(task)
        db.session.commit()

        if task.tries > 3:
            task.status = PersonaSplitRequestTaskStatus.FAILED
            db.session.add(task)
            db.session.commit()
            return

        prospect_id = task.prospect_id
        prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
        destination_client_archetype_ids = task.destination_client_archetype_ids
        archetypes = ClientArchetype.query.filter(
            ClientArchetype.id.in_(destination_client_archetype_ids)
        ).all()
        prospect_details = get_prospect_details(prospect.client_sdr_id, prospect_id)
        company_details = prospect_details.get('prospect_info', {}).get('company', {})

        persona_options_str = "\n".join(
            [
                "- {archetype_id}: {archetype}".format(
                    archetype_id=archetype.id, archetype=archetype.archetype
                )
                for archetype in archetypes
            ]
        )

        task.prompt = """
        I am splitting this Prospect into one of these personas:

        Persona Options:
        {persona_options_str}
        - 0: No match

        Here is the prospect information:
        - Full Name: {prospect_name}
        - Title: {prospect_title}
        - Company: {prospect_company}
        - Company Location: {prospect_company_location}
        - Company Description: {prospect_company_description}
        """.format(
            prospect_name=prospect.full_name,
            prospect_title=prospect.title,
            prospect_company=prospect.company,
            persona_options_str=persona_options_str,
            prospect_company_location=company_details.get('location', 'Unknown'),
            prospect_company_description=company_details.get('description', 'Unknown'),
        )

        output = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "system",
                    "content": task.prompt,
                },
                {
                    "role": "user",
                    "content": """
Which persona should I bucket into? Only include the number related to the persona. Nothing else.

Output a JSON object with two fields: "archetype_id" and "persona_id".

Output:""",
                },
            ],
            max_tokens=100,
        )

        task.raw_completion = output

        output_dict = json.loads(output)
        task.json_completion = output_dict

        archetype_id_number = output_dict["persona_id"]

        if (
            archetype_id_number == 0
            or archetype_id_number not in destination_client_archetype_ids
        ):
            raise Exception("Invalid archetype id")

        task.status = PersonaSplitRequestTaskStatus.COMPLETED
        prospect.archetype_id = archetype_id_number
        db.session.add(task)
        db.session.add(prospect)
        db.session.commit()

        return persona_options_str
    except Exception as e:
        db.session.rollback()

        raise self.retry(exc=e, countdown=2**self.request.retries)
