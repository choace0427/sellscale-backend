from src.prospecting.services import calculate_prospect_overall_status
from src.email_outbound.services import update_prospect_email_outreach_status
from src.message_generation.services import add_generated_msg_queue
from src.prospecting.nylas.services import nylas_get_messages, nylas_send_email
from src.email_outbound.models import ProspectEmailOutreachStatus
from src.utils.slack import send_slack_message, URL_MAP
from model_import import EmailSequenceStep, EmailSubjectLineTemplate, ProspectEmail, ProspectEmailStatusRecords
from app import db, celery
from src.client.models import ClientArchetype, ClientSDR, Prospect
from src.prospecting.models import ProspectOverallStatus, ProspectStatus
from typing import List, Optional
from sqlalchemy.sql.expression import func, or_
import datetime
from sqlalchemy.orm import joinedload
import markdown

def get_email_sequence_step_for_sdr(
    client_sdr_id: int,
    overall_statuses: Optional[list[ProspectOverallStatus]] = [],
    substatuses: Optional[list[str]] = [],
    client_archetype_ids: Optional[list[int]] = [],
    activeOnly: Optional[bool] = True,
) -> list[dict]:
    """Get all Email Sequence Steps for a given SDR and overall status

    Args:
        client_sdr_id (int): The id of the SDR
        overall_statuses (Optional[list[ProspectOverallStatus]], optional): The overall statuses of the email sequences. Defaults to [] which is ALL statuses.
        substatuses (Optional[list[str]], optional): The substatuses of the email sequences. Defaults to [] which is ALL substatuses.
        client_archetype_ids (Optional[list[int]], optional): The ids of the client archetypes. Defaults to [] which is ALL archetypes.
        activeOnly (Optional[bool], optional): Whether to only return active email sequences. Defaults to True.

    Returns:
        list[dict]: A list of email sequences
    """
    # If overall_statuses is not specified, grab all overall statuses
    if len(overall_statuses) == 0:
        overall_statuses = [pos for pos in ProspectOverallStatus]

    # If client_archetype_ids is not specified, grab all client archetypes
    if len(client_archetype_ids) == 0:
        client_archetype_ids = [
            ca.id
            for ca in ClientArchetype.query.filter_by(client_sdr_id=client_sdr_id).all()
        ]

    steps: list[EmailSequenceStep] = EmailSequenceStep.query.filter(
        EmailSequenceStep.client_sdr_id == client_sdr_id,
        EmailSequenceStep.client_archetype_id.in_(client_archetype_ids),
        EmailSequenceStep.overall_status.in_(overall_statuses),
    )

    # If substatuses is specified, filter by substatuses
    if len(substatuses) > 0:
        steps = steps.filter(EmailSequenceStep.substatus.in_(substatuses))

    # If activeOnly is specified, filter by active
    if activeOnly:
        steps = steps.filter(EmailSequenceStep.active == True)

    steps: list[EmailSequenceStep] = steps.all()

    return [step.to_dict() for step in steps]


def get_sequence_step_count_for_sdr(
    client_sdr_id: int, client_archetype_ids: Optional[list[int]] = []
) -> dict:
    """Gets the counts for email sequences that belong to a Client SDR in a given archetype.

    Args:
        client_sdr_id (int): _description_
        client_archetype_ids (Optional[list[int]], optional): Which archetypes to retrieve the email sequences. Defaults to all archetypes.
    """
    sequence_steps = get_email_sequence_step_for_sdr(
        client_sdr_id, client_archetype_ids=client_archetype_ids
    )

    counts = {
        "total": len(sequence_steps),
        ProspectOverallStatus.ACCEPTED.value: 0,
        ProspectOverallStatus.BUMPED.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUESTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED.value: 0,
        ProspectStatus.ACTIVE_CONVO_OBJECTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS.value: 0,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING.value: 0,
        ProspectStatus.ACTIVE_CONVO_REVIVAL.value: 0,
    }
    for sequence_step in sequence_steps:
        if sequence_step.get("overall_status") in counts:
            counts[sequence_step.get("overall_status")] += 1
        if sequence_step.get("substatus") in counts:
            counts[sequence_step.get("substatus")] += 1

    return counts


def create_email_sequence_step(
    client_sdr_id: int,
    client_archetype_id: int,
    title: str,
    template: str,
    overall_status: ProspectOverallStatus,
    bumped_count: int = None,
    active: bool = True,
    substatus: Optional[str] = None,
    default: Optional[bool] = False,
    sellscale_default_generated: Optional[bool] = False,
) -> int:
    """Create a new email sequence, if default is True, set all other email sequences to False

    Args:
        client_sdr_id (int): The id of the SDR
        client_archetype_id (int): The id of the client archetype
        title (str): The title of the email sequence
        template (str): The template of the email sequence
        overall_status (ProspectOverallStatus): The overall status of the email sequence
        bumped_count (int, optional): The number which corresponds to which bump in the sequence this step appears. Defaults to None.
        active (bool, optional): Whether the email sequence is active. Defaults to True.
        substatus (Optional[str], optional): The substatus of the email sequence. Defaults to None.
        default (Optional[bool], optional): Whether the email sequence is the default. Defaults to False.
        sellscale_default_generated (Optional[bool], optional): Whether the email sequence was generated by SellScale. Defaults to False.

    Returns:
        int: The id of the newly created email sequence
    """
    if default:
        all_sequence_steps: list[
            EmailSequenceStep
        ] = EmailSequenceStep.query.filter_by(
            client_sdr_id=client_sdr_id,
            client_archetype_id=client_archetype_id,
            overall_status=overall_status,
        )
        if overall_status == ProspectOverallStatus.BUMPED and bumped_count is not None:
            all_sequence_steps = all_sequence_steps.filter_by(
                bumped_count=bumped_count
            )
        all_sequence_steps = all_sequence_steps.all()
        for sequence_step in all_sequence_steps:
            sequence_step.default = False
            db.session.add(sequence_step)

    # Create the email sequence
    sequence_step = EmailSequenceStep(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        title=title,
        overall_status=overall_status,
        substatus=substatus,
        bumped_count=bumped_count,
        active=active,
        default=default,
        sellscale_default_generated=sellscale_default_generated,
        template=template,
    )
    db.session.add(sequence_step)
    db.session.commit()
    sequence_step_id = sequence_step.id

    return sequence_step_id


def modify_email_sequence_step(
    client_sdr_id: int,
    client_archetype_id: int,
    sequence_step_id: int,
    title: Optional[str],
    template: Optional[str],
    bumped_count: Optional[int] = None,
    default: Optional[bool] = False,
) -> bool:
    """Modify a email sequence

    Args:
        client_sdr_id (int): The id of the client SDR
        client_archetype_id(int): The id of the client Archetype
        sequence_step_id (int): The id of the email sequence
        title (Optional[str]): The title of the email sequence
        template (Optional[str]): The template of the email sequence
        bumped_count (Optional[int], optional): The number which corresponds to which bump in the sequence this step appears. Defaults to None.
        default (Optional[bool]): Whether the email sequence is the default

    Returns:
        bool: Whether the email sequence was modified
    """
    sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
        EmailSequenceStep.client_sdr_id == client_sdr_id,
        EmailSequenceStep.id == sequence_step_id,
    ).first()

    if title:
        sequence_step.title = title
    if template:
        sequence_step.template = template

    if bumped_count:
        sequence_step.bumped_count = bumped_count

    overall_status = sequence_step.overall_status
    substatus = sequence_step.substatus

    if default:
        default_sequence_steps: list[
            EmailSequenceStep
        ] = EmailSequenceStep.query.filter(
            EmailSequenceStep.client_sdr_id == client_sdr_id,
            EmailSequenceStep.client_archetype_id == client_archetype_id,
            EmailSequenceStep.overall_status == overall_status,
            EmailSequenceStep.default == True,
        )
        if substatus:
            default_sequence_steps = default_sequence_steps.filter(
                EmailSequenceStep.substatus == substatus
            )

        if overall_status == ProspectOverallStatus.BUMPED and bumped_count is not None:
            default_sequence_steps = default_sequence_steps.filter(
                EmailSequenceStep.bumped_count == bumped_count
            )
        default_sequence_steps = default_sequence_steps.all()
        for default_sequence_step in default_sequence_steps:
            default_sequence_step.default = False
            db.session.add(default_sequence_step)
    sequence_step.default = default

    db.session.add(sequence_step)
    db.session.commit()

    return True


def deactivate_sequence_step(client_sdr_id: int, sequence_step_id: int) -> bool:
    """Deletes a BumpFramework entry by marking it as inactive

    Args:
        sequence_step_id (int): The id of the BumpFramework to delete

    Returns:
        bool: Whether the BumpFramework was deleted
    """
    sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
        EmailSequenceStep.id == sequence_step_id,
        EmailSequenceStep.client_sdr_id == client_sdr_id,
    ).first()

    # Can't deactive the sellscale generated default frameworks
    if sequence_step.sellscale_default_generated:
        return False

    sequence_step.active = False
    db.session.add(sequence_step)
    db.session.commit()

    return True


def activate_sequence_step(client_sdr_id: int, sequence_step_id: int) -> bool:
    """Activates a BumpFramework entry by marking it as active

    Args:
        sequence_step_id (int): The id of the BumpFramework to activate

    Returns:
        None
    """
    sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
        EmailSequenceStep.id == sequence_step_id,
        EmailSequenceStep.client_sdr_id == client_sdr_id,
    ).first()
    sequence_step.active = True
    db.session.add(sequence_step)
    db.session.commit()

    return True


def get_email_subject_line_template(
    client_sdr_id: int,
    client_archetype_id: int,
    active_only: Optional[bool] = True,
) -> list[dict]:
    """Gets all email subject line templates for a given SDR and archetype

    Args:
        client_sdr_id (int): The id of the SDR
        client_archetype_id (int): The id of the archetype
        active_only (Optional[bool], optional): Whether to only return active email subject line templates. Defaults to True.

    Returns:
        list[dict]: A list of email subject line templates
    """
    templates: list[EmailSubjectLineTemplate] = EmailSubjectLineTemplate.query.filter(
        EmailSubjectLineTemplate.client_sdr_id == client_sdr_id,
        EmailSubjectLineTemplate.client_archetype_id == client_archetype_id,
    )

    # If activeOnly is specified, filter by active
    if active_only:
        templates = templates.filter(EmailSubjectLineTemplate.active == True)

    templates: list[EmailSubjectLineTemplate] = templates.all()

    return [template.to_dict() for template in templates]


def create_email_subject_line_template(
    client_sdr_id: int,
    client_archetype_id: int,
    subject_line: str,
    active: bool = True,
    sellscale_generated: bool = False,
) -> int:
    """Create a new email subject line template

    Args:
        client_sdr_id (int): The id of the SDR
        client_archetype_id (int): The id of the archetype
        subject_line (str): The subject line of the email subject line template
        active (bool, optional): Whether the email subject line template is active. Defaults to True.
        sellscale_generated (bool, optional): Whether the email subject line template was generated by SellScale. Defaults to False.

    Returns:
        int: The id of the newly created email subject line template
    """
    # Create the email subject line template
    template = EmailSubjectLineTemplate(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        subject_line=subject_line,
        active=active,
        sellscale_generated=sellscale_generated,
    )
    db.session.add(template)
    db.session.commit()
    template_id = template.id

    return template_id


def modify_email_subject_line_template(
    client_sdr_id: int,
    client_archetype_id: int,
    email_subject_line_template_id: int,
    subject_line: Optional[str],
    active: Optional[bool] = True,
) -> bool:
    """Modify a email subject line template

    Args:
        client_sdr_id (int): The id of the client SDR
        client_archetype_id(int): The id of the client Archetype
        email_subject_line_template_id (int): The id of the email subject line template
        subject_line (Optional[str]): The subject line of the email subject line template
        active (Optional[bool], optional): Whether the email subject line template is active. Defaults to True.

    Returns:
        bool: Whether the email subject line template was modified
    """
    template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.filter(
        EmailSubjectLineTemplate.client_sdr_id == client_sdr_id,
        EmailSubjectLineTemplate.id == email_subject_line_template_id,
        EmailSubjectLineTemplate.client_archetype_id == client_archetype_id,
    ).first()
    if not template:
        return False

    if subject_line:
        template.subject_line = subject_line
    template.active = active

    db.session.add(template)
    db.session.commit()

    return True


def deactivate_email_subject_line_template(
    client_sdr_id: int, email_subject_line_template_id: int
) -> bool:
    """Deletes a EmailSubjectLineTemplate entry by marking it as inactive

    Args:
        email_subject_line_template_id (int): The id of the EmailSubjectLineTemplate to delete

    Returns:
        bool: Whether the EmailSubjectLineTemplate was deleted
    """
    template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.filter(
        EmailSubjectLineTemplate.id == email_subject_line_template_id,
        EmailSubjectLineTemplate.client_sdr_id == client_sdr_id,
    ).first()

    template.active = False
    db.session.add(template)
    db.session.commit()

    return True


def activate_email_subject_line_template(
    client_sdr_id: int, email_subject_line_template_id: int
) -> bool:
    """Activates a EmailSubjectLineTemplate entry by marking it as active

    Args:
        email_subject_line_template_id (int): The id of the EmailSubjectLineTemplate to activate

    Returns:
        None
    """
    template: EmailSubjectLineTemplate = EmailSubjectLineTemplate.query.filter(
        EmailSubjectLineTemplate.id == email_subject_line_template_id,
        EmailSubjectLineTemplate.client_sdr_id == client_sdr_id,
    ).first()
    template.active = True
    db.session.add(template)
    db.session.commit()

    return True


def generate_prospect_email_bump(
        client_sdr_id: int,
        prospect_id: int,
        thread_id: int,
        override_sequence_id: Optional[int] = None,
        override_template: Optional[str] = None
    ):
    """Generates a follow up email message for a prospect

    Args:
        client_sdr_id (int): Client SDR ID
        prospect_id (int): Prospect ID
        thread_id (int): Email Thread ID
    """
    from src.message_generation.email.services import ai_followup_email_prompt, generate_email

    try:
        
        prompt = ai_followup_email_prompt(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            thread_id=thread_id,
            override_sequence_id=override_sequence_id,
            override_template=override_template
        )
        if not prompt: return None
        
        email_body = generate_email(prompt)
        email_body = email_body.get('body')

        return { 'prompt': prompt, 'completion': email_body }

    except Exception as e:
        send_slack_message(
            message=f"🛑 *Error occurred:* '{e}'",
            webhook_urls=[URL_MAP["operations-auto-bump-email"]],
        )
        return None


@celery.task
def generate_email_bumps():
    
    BUMP_DELAY_DAYS = 3 # TODO: Hardcoded for now, but should be a setting in steps

    # For each prospect that's in one of the states (and client sdr has auto_generate_messages enabled)
    sdrs: List[ClientSDR] = (
        ClientSDR.query.filter(
            ClientSDR.active == True,
            ClientSDR.auto_generate_messages == True,
            ClientSDR.auto_bump == True,
            ClientSDR.id == 34, # temp
        )
        .order_by(func.random())
        .all()
    )

    for sdr in sdrs:
        prospects: List[Prospect] = Prospect.query.filter(
            Prospect.client_sdr_id == sdr.id,
            Prospect.overall_status.in_(
                [
                    "SENT_OUTREACH",
                    "ACCEPTED",
                    "BUMPED",
                ]
            ),
            or_(
                Prospect.hidden_until == None,
                Prospect.hidden_until <= datetime.datetime.utcnow(),
            ),
            Prospect.active == True,
        ).all()
        # ).join(ProspectEmail).filter(
        #     ProspectEmail.outreach_status.in_(
        #         [
        #             "ACCEPTED",
        #             "EMAIL_OPENED",
        #         ]
        #     )
        # ).all()

        # print(f"Generating bumps for {len(prospects)} prospects...")

        for prospect in prospects:

            # Get the archetype
            archetype: ClientArchetype = ClientArchetype.query.get(
                prospect.archetype_id
            )

            # If the archetype is unassigned contact, then we don't generate a bump
            if archetype.is_unassigned_contact_archetype:
                continue
            

            # Get the prospect email
            prospect_email: ProspectEmail = ProspectEmail.query.get(
                prospect.approved_prospect_email_id
            )
            if not prospect_email:
                continue

            # CHECK: If the prospect is in ACCEPTED stage and the message delay on the archetype is not quite up
            #      then we don't generate a bump
            if prospect.overall_status == ProspectOverallStatus.ACCEPTED:

                # If the archetype has a message delay, check if it's been long enough by referencing status records
                if archetype and archetype.first_message_delay_days:
                    # Get the first status record
                    status_record: ProspectEmailStatusRecords = (
                        ProspectEmailStatusRecords.query.filter(
                            ProspectEmailStatusRecords.prospect_email_id == prospect_email.id,
                            ProspectEmailStatusRecords.to_status == ProspectEmailOutreachStatus.ACCEPTED,
                        )
                        .order_by(ProspectEmailStatusRecords.created_at.asc())
                        .first()
                    )
                    if status_record:
                        # If the first status record is less than the delay, then we don't generate a bump
                        if (
                            datetime.datetime.utcnow() - status_record.created_at
                        ).days < archetype.first_message_delay_days:
                            continue
                        
            # If bumping, check if the bump delay has been met
            if prospect.overall_status == ProspectOverallStatus.BUMPED and False:
                # Check if last message that was sent out was over X days ago
                from model_import import EmailConversationMessage

                latest_message: EmailConversationMessage = EmailConversationMessage.query.filter_by(
                    prospect_id=prospect.id
                ).order_by(EmailConversationMessage.date_received.desc()).first()
                if latest_message:
                    if (datetime.datetime.utcnow() - latest_message.date_received).days < BUMP_DELAY_DAYS:
                        #print(f"Skipping bump for prospect #{prospect.id} because last message was sent less than {BUMP_DELAY_DAYS} days ago")
                        continue

            # Generate the email bump
            data = generate_prospect_email_bump(
                client_sdr_id=prospect.client_sdr_id,
                prospect_id=prospect.id,
                thread_id=prospect_email.nylas_thread_id,
            )
            if not data: continue

            # Get last message of thread to reply to
            messages = nylas_get_messages(
                client_sdr_id=prospect.client_sdr_id,
                prospect_id=prospect.id,
                thread_id=prospect_email.nylas_thread_id,
            )
            last_message = messages[-1] if len(messages) > 0 else { "body": "", "nylas_message_id": None }

            # Convert completion markdown to body html
            body = markdown.markdown(data.get("completion").replace('\n', '<br/>'))

            # Send the email
            result = nylas_send_email(
                client_sdr_id=prospect.client_sdr_id,
                prospect_id=prospect.id,
                subject="Empty subject line",
                body=body,
                reply_to_message_id=last_message.get("nylas_message_id"),
                prospect_email_id=prospect_email.id,
            )
            nylas_message_id = result.get("id")
            if isinstance(nylas_message_id, str):
                add_generated_msg_queue(
                    client_sdr_id=prospect.client_sdr_id, nylas_message_id=nylas_message_id
                )

            # IMPORTANT: this short circuits this loop if we successfully generate a bump
            #       that way it only generates a bump once every 2 minutes
            if result.get("thread_id"):
                message_id = result.get("id")
                thread_id = result.get("thread_id")
                email_to = result.get("to")[0]

                send_slack_message(
                    message=f"•••: ✅ SDR {sdr.name} (#{sdr.id}): Sending autogenerated bump email to prospect {prospect.full_name} (#{prospect.id}) 🤖\nLast Message: {last_message.get('body')}\nMessage: {data.get('completion')}",
                    webhook_urls=[URL_MAP["operations-auto-bump-email"]],
                    blocks=[
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"✅ SDR {sdr.name} (#{sdr.id}): Sending autogenerated bump email",
                                "emoji": True,
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"--- *Archetype*: {archetype.archetype}, (#{archetype.id}) ---",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"--- Conversation with prospect *{prospect.full_name}* (#{prospect.id}) ---",
                            },
                        },
                        {"type": "divider"},
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "*Most recent message*: "
                                    + last_message.get("body"),
                                },
                            ],
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Autobump Message [markdown]* {data.get('completion')}*",
                                },
                            ],
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Autobump Message [html]* {result.get('body')}*",
                                },
                            ],
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Prompt* {data.get('prompt')}*",
                                },
                            ],
                        },
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"--- Nylas Msg ID: *{message_id}*, Thread ID: *{thread_id}* ---",
                            },
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"Email to: {email_to.get('email')} ({email_to.get('name')})",
                                },
                            ],
                        },
                    ],
                )

                # Set status to bumped
                update_prospect_email_outreach_status(
                    prospect_email_id=prospect_email.id,
                    new_status=ProspectEmailOutreachStatus.BUMPED
                )
                
                # Increase times bumped
                if prospect_email.times_bumped is None:
                    prospect_email.times_bumped = 1
                else:
                    prospect_email.times_bumped += 1
                db.session.add(prospect_email)
                db.session.commit()

                calculate_prospect_overall_status(prospect_id=prospect.id)

                return
