from typing import Optional
from src.email_outbound.models import ProspectEmailStatus

from src.ml.services import get_text_generation

from src.ml.openai_wrappers import OPENAI_CHAT_GPT_3_5_TURBO_MODEL

from src.bump_framework.services import clone_bump_framework
from src.message_generation.services import create_cta

from src.client.services import (
    create_client_archetype,
)
from src.company.models import Company
from src.message_generation.models import GeneratedMessageStatus
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from model_import import (
    PersonaSplitRequest,
    PersonaSplitRequestTask,
    PersonaSplitRequestTaskStatus,
    ClientArchetype,
    Prospect,
    ClientSDR,
    GeneratedMessageCTA,
    BumpFramework,
    StackRankedMessageGenerationConfiguration,
    EmailSequenceStep,
)
from src.li_conversation.models import (
    LinkedInInitialMessageToAssetMapping,
    LinkedinInitialMessageTemplate,
)
from src.prospecting.icp_score.services import (
    apply_icp_scoring_ruleset_filters_task,
    clone_icp_ruleset,
)
from src.prospecting.models import ProspectStatus
from src.prospecting.services import get_prospect_details
from app import db, celery
import json
import yaml
from sqlalchemy import func

from src.research.account_research import generate_prospect_research
from src.client.archetype.services_client_archetype import (
    create_linkedin_initial_message_template,
)
from src.email_sequencing.services import create_email_sequence_step


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
    for index, task in enumerate(tasks):
        process_persona_split_request_task.apply_async(
            args=[task.id, index], countdown=index
        )

    return True, "OK"


def get_recent_split_requests(client_sdr_id: int, source_archetype_id: int):
    """
    Given a client sdr id, return a list of recent split requests
    """
    query = (
        db.session.query(
            PersonaSplitRequest.created_at,
            PersonaSplitRequest.updated_at,
            PersonaSplitRequest.id,
            PersonaSplitRequest.client_sdr_id,
            PersonaSplitRequest.source_client_archetype_id,
            PersonaSplitRequest.destination_client_archetype_ids,
            func.count()
            .filter(PersonaSplitRequestTask.status == "QUEUED")
            .label("queued"),
            func.count()
            .filter(PersonaSplitRequestTask.status == "IN_PROGRESS")
            .label("in_progress"),
            func.count()
            .filter(PersonaSplitRequestTask.status == "COMPLETED")
            .label("completed"),
            func.count()
            .filter(PersonaSplitRequestTask.status == "FAILED")
            .label("failed"),
            func.count()
            .filter(PersonaSplitRequestTask.status == "NO_MATCH")
            .label("no_match"),
        )
        .join(
            PersonaSplitRequestTask,
            PersonaSplitRequestTask.persona_split_request_id == PersonaSplitRequest.id,
        )
        .filter(
            PersonaSplitRequest.client_sdr_id == client_sdr_id,
            PersonaSplitRequest.source_client_archetype_id == source_archetype_id,
        )
        .group_by(
            PersonaSplitRequest.created_at,
            PersonaSplitRequest.updated_at,
            PersonaSplitRequest.id,
            PersonaSplitRequest.client_sdr_id,
            PersonaSplitRequest.source_client_archetype_id,
            PersonaSplitRequest.destination_client_archetype_ids,
        )
        .order_by(PersonaSplitRequest.created_at.desc())
        .limit(5)
    )

    # Execute the query and fetch the results
    results = query.all()

    parsed_results = []
    for result in results:
        (
            created_at,
            updated_at,
            id,
            client_sdr_id,
            source_client_archetype_id,
            destination_client_archetype_ids,
            queued,
            in_progress,
            completed,
            failed,
            no_match,
        ) = result
        parsed_result = {
            "id": id,
            "created_at": created_at,
            "client_sdr_id": client_sdr_id,
            "source_client_archetype_id": source_client_archetype_id,
            "destination_client_archetype_ids": destination_client_archetype_ids,
            "num_queued": queued,
            "num_in_progress": in_progress,
            "num_completed": completed,
            "num_failed": failed,
            "num_no_match": no_match,
        }
        parsed_results.append(parsed_result)

    return parsed_results


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
def process_persona_split_request_task(self, task_id: int, countdown: int = 0):
    """
    Given a task id, process the task
    """

    try:
        task: PersonaSplitRequestTask = PersonaSplitRequestTask.query.filter_by(
            id=task_id
        ).first()
        task.tries += 1

        if task is None:
            return
        if task.status in [
            PersonaSplitRequestTaskStatus.COMPLETED,
            PersonaSplitRequestTaskStatus.FAILED,
        ]:
            return

        if task.status in [PersonaSplitRequestTaskStatus.NO_MATCH] and task.tries > 3:
            return

        if task.tries > 3:
            task.status = PersonaSplitRequestTaskStatus.FAILED
            db.session.add(task)
            db.session.commit()
            return

        task.status = PersonaSplitRequestTaskStatus.IN_PROGRESS
        db.session.add(task)
        db.session.commit()

        prospect_id = task.prospect_id
        prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
        destination_client_archetype_ids = task.destination_client_archetype_ids
        archetypes = ClientArchetype.query.filter(
            ClientArchetype.id.in_(destination_client_archetype_ids)
        ).all()

        company: Company = Company.query.filter_by(id=prospect.company_id).first()
        company_loc_str = ""
        if company:
            if company.locations and len(company.locations) > 0:
                company_loc = company.locations[0]
                company_loc_str = f'{company_loc.get("city", "")}, {company_loc.get("geographicArea", "")} {company_loc.get("country", "")}, Postal Code: {company_loc.get("postalCode", "")}'

        persona_options_str = "\n".join(
            [
                "- {archetype_id}: {archetype} (description: {archetype_icp_matching_prompt})".format(
                    archetype_id=archetype.id,
                    archetype=archetype.archetype,
                    archetype_icp_matching_prompt=archetype.icp_matching_prompt,
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
            prospect_company_location=company_loc_str,
            prospect_company_description=company.description if company else "",
        )

        output = get_text_generation(
            [
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
            model=OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
            max_tokens=100,
            type="MISC_CLASSIFY",
        )

        task.raw_completion = output

        output_dict = yaml.safe_load(output)
        task.json_completion = output_dict

        archetype_id_number = output_dict["persona_id"]

        if archetype_id_number == 0:
            task.status = PersonaSplitRequestTaskStatus.NO_MATCH
            db.session.add(task)
            db.session.commit()
            raise Exception("No match")

        if archetype_id_number not in destination_client_archetype_ids:
            raise Exception("Invalid archetype id")

        task.status = PersonaSplitRequestTaskStatus.COMPLETED
        old_archetype_id = prospect.archetype_id
        prospect.archetype_id = archetype_id_number
        client_sdr_id = prospect.client_sdr_id
        prospect_id = prospect.id
        db.session.add(task)
        db.session.add(prospect)
        db.session.commit()

        # If the new archetype is different from the old archetype, clear and rerun the
        # prospect's ICP fit and account research
        if old_archetype_id != archetype_id_number:
            apply_icp_scoring_ruleset_filters_task(
                client_archetype_id=archetype_id_number,
                prospect_ids=[prospect_id],
            )
            generate_prospect_research(prospect_id, False, True)

        return persona_options_str
    except Exception as e:
        db.session.rollback()

        raise self.retry(exc=e, countdown=10**self.request.retries)


def get_unassignable_prospects_using_icp_heuristic(
    client_sdr_id: int, client_archetype_id: int
) -> tuple[list[int], list[dict], int]:
    """Gets a list of prospects that should be unassigned from a persona using the ICP heuristic

    ICP Heuristic: Unassign prospects that are LOW or VERY_LOW

    Args:
        client_sdr_id (int): ID of the Client SDR
        client_archetype_id (int): ID of the Client Archetype

    Returns:
        list[int]: List of prospect IDs that should be unassigned
        list[dict]: List of prospect dictionaries that should be unassigned
        int: Total count of prospects that should be unassigned
    """
    # Get the target archetype
    target_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if target_archetype is None:
        return []

    # Get the prospects that should be unassigned
    prospects_to_unassign: list[Prospect] = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
        Prospect.archetype_id == client_archetype_id,
        Prospect.icp_fit_score.in_([0, 1]),
    )

    # Get the count
    total_count = prospects_to_unassign.count()
    prospects_to_unassign = prospects_to_unassign.limit(10).all()
    if len(prospects_to_unassign) == 0:
        return [], [], total_count

    return (
        [prospect.id for prospect in prospects_to_unassign],
        [prospect.to_dict(shallow_data=True) for prospect in prospects_to_unassign],
        total_count,
    )


@celery.task(bind=True, max_retries=3)
def unassign_prospects(
    self,
    client_sdr_id: int,
    client_archetype_id: int,
    use_icp_heuristic: bool = True,
    manual_unassign_list: Optional[list] = [],
) -> bool:
    """Unassigns prospects from a persona, placing them into the Unassigned persona

    Args:
        client_sdr_id (int): ID of the SDR
        client_archetype_id (int): ID of the persona to unassign prospects from
        use_icp_heuristic (bool, optional): Whether or not to use the ICP heuristic. Defaults to True.
        manual_unassign_list (Optional[list], optional): List of prospect IDs to manually unassign. Defaults to [].

    Returns:
        bool: True if successful, False otherwise
    """
    from src.message_generation.models import GeneratedMessage
    from src.email_outbound.models import ProspectEmail

    # Get the target archetype
    target_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if target_archetype is None:
        return False

    # Get the unassigned archetype
    unassigned_archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
        ClientArchetype.is_unassigned_contact_archetype == True,
    ).first()
    unassigned_archetype_id = unassigned_archetype.id
    if unassigned_archetype is None:
        return False

    # Grab the prospects to unassign
    unassign_prospects: list[Prospect] = []

    # Grab the manual prospects to unassign
    manual_prospect_list: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(manual_unassign_list)
    ).all()
    unassign_prospects.extend(manual_prospect_list)

    # Use the ICP Heuristic (ICP score must be LOW or VERY LOW)
    # LOW: ICP score 0
    # VERY LOW: ICP score 1
    if use_icp_heuristic:
        low_icp_prospects = Prospect.query.filter(
            Prospect.client_sdr_id == client_sdr_id,
            Prospect.archetype_id == target_archetype.id,
            Prospect.icp_fit_score.in_([0, 1]),
        ).all()
        unassign_prospects.extend(low_icp_prospects)

    # Unassign the contacts by reassigning to the "Unassigned" archetype
    for prospect in unassign_prospects:
        prospect.archetype_id = unassigned_archetype_id
        prospect.icp_fit_error = None
        prospect.icp_fit_score = None
        prospect.icp_fit_reason = None
        prospect.icp_fit_prompt_data = None

        # LinkedIn: Before deleting messages, we need to make sure the prospect is only in PROSPECTED or QUEUED status
        if (
            prospect.status == ProspectStatus.PROSPECTED
            or prospect.status == ProspectStatus.QUEUED_FOR_OUTREACH
        ):
            # IF the prospect has a generated message, delete the message and clear the ID
            if prospect.approved_outreach_message_id is not None:
                prospect_message: GeneratedMessage = GeneratedMessage.query.get(
                    prospect.approved_outreach_message_id
                )
                if prospect_message is not None:
                    prospect_message.message_status = GeneratedMessageStatus.BLOCKED
                prospect.approved_outreach_message_id = None

        if prospect.approved_prospect_email_id is not None:
            prospect_email: ProspectEmail = ProspectEmail.query.get(
                prospect.approved_prospect_email_id
            )
            if prospect_email is not None:
                # EMAIL: Before deleting, we need to make sure the email has not been sent
                if prospect_email.email_status == ProspectEmailStatus.SENT:
                    prospect_email.date_scheduled_to_send = None
                    if prospect_email.personalized_body is not None:
                        personalized_body: GeneratedMessage = (
                            GeneratedMessage.query.get(prospect_email.personalized_body)
                        )
                        if personalized_body is not None:
                            personalized_body.message_status = (
                                GeneratedMessageStatus.BLOCKED
                            )
                        prospect_email.personalized_body = None
                    if prospect_email.personalized_first_line is not None:
                        personalized_first_line: GeneratedMessage = (
                            GeneratedMessage.query.get(
                                prospect_email.personalized_first_line
                            )
                        )
                        if personalized_first_line is not None:
                            personalized_first_line.message_status = (
                                GeneratedMessageStatus.BLOCKED
                            )
                        prospect_email.personalized_first_line = None
                    if prospect_email.personalized_subject_line is not None:
                        personalized_subject_line: GeneratedMessage = (
                            GeneratedMessage.query.get(
                                prospect_email.personalized_subject_line
                            )
                        )
                        if personalized_subject_line is not None:
                            personalized_subject_line.message_status = (
                                GeneratedMessageStatus.BLOCKED
                            )
                        prospect_email.personalized_subject_line = None

                    prospect.approved_prospect_email_id = None

        db.session.commit()

    return True


def clone_persona(
    client_sdr_id: int,
    original_persona_id: int,
    persona_name: str,
    persona_fit_reason: str,
    persona_icp_matching_instructions: str,
    persona_contact_objective: str,
    option_ctas: bool,
    option_bump_frameworks: bool,
    option_voices: bool,
    option_email_blocks: bool,
    option_icp_filters: bool,
    option_email_steps: bool,
    option_li_init_msg: bool,
):
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if sdr is None:
        return None

    original_persona: ClientArchetype = ClientArchetype.query.get(original_persona_id)
    if original_persona is None:
        return None

    result = create_client_archetype(
        client_id=sdr.client_id,
        client_sdr_id=client_sdr_id,
        archetype=persona_name,
        filters=None,
        base_archetype_id=original_persona_id,
        disable_ai_after_prospect_engaged=True,
        persona_fit_reason=persona_fit_reason,
        icp_matching_prompt=persona_icp_matching_instructions,
        persona_contact_objective=persona_contact_objective,
        template_mode=original_persona.template_mode,
    )
    new_persona_id: int = result.get("client_archetype_id") or -1

    if new_persona_id == -1:
        print("Failed to create new persona")
        return None

    if option_ctas:
        original_ctas: list[GeneratedMessageCTA] = GeneratedMessageCTA.query.filter_by(
            archetype_id=original_persona_id
        ).all()
        for original_cta in original_ctas:
            cta = create_cta(
                archetype_id=new_persona_id,
                text_value=original_cta.text_value,
                expiration_date=original_cta.expiration_date,
                active=original_cta.active,
            )

    if option_li_init_msg:
        li_init_msgs: list[LinkedinInitialMessageTemplate] = (
            LinkedinInitialMessageTemplate.query.filter_by(
                client_archetype_id=original_persona_id
            ).all()
        )
        for li_init_msg in li_init_msgs:
            create_linkedin_initial_message_template(
                title=li_init_msg.title,
                message=li_init_msg.message,
                client_sdr_id=li_init_msg.client_sdr_id,
                client_archetype_id=new_persona_id,
                research_points=li_init_msg.research_points,
                additional_instructions=li_init_msg.additional_instructions,
            )

    if option_bump_frameworks:
        original_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter_by(
            client_archetype_id=original_persona_id
        ).all()
        for original_bump_framework in original_bump_frameworks:
            new_id = clone_bump_framework(
                client_sdr_id=client_sdr_id,
                bump_framework_id=original_bump_framework.id,
                target_archetype_id=new_persona_id,
            )

    if option_voices:
        original_voices: list[StackRankedMessageGenerationConfiguration] = (
            StackRankedMessageGenerationConfiguration.query.filter_by(
                archetype_id=original_persona_id
            ).all()
        )
        for original_voice in original_voices:
            voice = StackRankedMessageGenerationConfiguration(
                configuration_type=original_voice.configuration_type,
                generated_message_type=original_voice.generated_message_type,
                research_point_types=original_voice.research_point_types,
                instruction=original_voice.instruction,
                computed_prompt=original_voice.computed_prompt,
                active=original_voice.active,
                always_enable=original_voice.always_enable,
                name=original_voice.name,
                client_id=original_voice.client_id,
                archetype_id=new_persona_id,
                priority=original_voice.priority,
                prompt_1=original_voice.prompt_1,
                completion_1=original_voice.completion_1,
                prompt_2=original_voice.prompt_2,
                completion_2=original_voice.completion_2,
                prompt_3=original_voice.prompt_3,
                completion_3=original_voice.completion_3,
                prompt_4=original_voice.prompt_4,
                completion_4=original_voice.completion_4,
                prompt_5=original_voice.prompt_5,
                completion_5=original_voice.completion_5,
                prompt_6=original_voice.prompt_6,
                completion_6=original_voice.completion_6,
                prompt_7=original_voice.prompt_7,
                completion_7=original_voice.completion_7,
            )
            db.session.add(voice)
        db.session.commit()

    if option_email_blocks:
        persona: ClientArchetype = ClientArchetype.query.get(new_persona_id)
        original_persona: ClientArchetype = ClientArchetype.query.get(
            original_persona_id
        )
        persona.email_blocks_configuration = original_persona.email_blocks_configuration
        db.session.commit()

    if option_email_steps:
        email_sequence_steps: list[EmailSequenceStep] = (
            EmailSequenceStep.query.filter_by(
                client_archetype_id=original_persona_id
            ).all()
        )
        for email_sequence_step in email_sequence_steps:
            create_email_sequence_step(
                client_sdr_id=email_sequence_step.client_sdr_id,
                client_archetype_id=new_persona_id,
                title=email_sequence_step.title,
                template=email_sequence_step.template,
                overall_status=email_sequence_step.overall_status,
                bumped_count=email_sequence_step.bumped_count,
                active=email_sequence_step.active,
                substatus=email_sequence_step.substatus,
                default=email_sequence_step.default,
                sellscale_default_generated=email_sequence_step.sellscale_default_generated,
                transformer_blocklist=email_sequence_step.transformer_blocklist,
                sequence_delay_days=email_sequence_step.sequence_delay_days,
                mapped_asset_ids=[],
            )

    if option_icp_filters:
        clone_icp_ruleset(
            source_archetype_id=original_persona_id,
            target_archetype_id=new_persona_id,
        )

    return persona
