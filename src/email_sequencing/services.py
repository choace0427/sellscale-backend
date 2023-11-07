from model_import import (
    EmailSequenceStep,
    EmailSubjectLineTemplate,
)
from app import db
from src.client.models import ClientArchetype
from src.email_sequencing.models import EmailTemplatePool, EmailTemplateType
from src.prospecting.models import ProspectOverallStatus, ProspectStatus
from typing import List, Optional

from src.research.models import ResearchPointType


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
    transformer_blocklist: Optional[list] = [],
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
        transformer_blocklist (Optional[list], optional): The blocklist of transformer types. Defaults to [].

    Returns:
        int: The id of the newly created email sequence
    """
    if default:
        all_sequence_steps: list[EmailSequenceStep] = EmailSequenceStep.query.filter_by(
            client_sdr_id=client_sdr_id,
            client_archetype_id=client_archetype_id,
            overall_status=overall_status,
        )
        if overall_status == ProspectOverallStatus.BUMPED and bumped_count is not None:
            all_sequence_steps = all_sequence_steps.filter_by(bumped_count=bumped_count)
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
        transformer_blocklist=transformer_blocklist,
    )
    db.session.add(sequence_step)
    db.session.commit()
    sequence_step_id = sequence_step.id

    return sequence_step_id


def modify_email_sequence_step(
    client_sdr_id: int,
    client_archetype_id: int,
    sequence_step_id: int,
    title: Optional[str] = None,
    template: Optional[str] = None,
    sequence_delay_days: Optional[int] = None,
    bumped_count: Optional[int] = None,
    default: Optional[bool] = False,
    transformer_blocklist: Optional[list] = [],
) -> bool:
    """Modify a email sequence

    Args:
        client_sdr_id (int): The id of the client SDR
        client_archetype_id(int): The id of the client Archetype
        sequence_step_id (int): The id of the email sequence
        title (Optional[str]): The title of the email sequence
        template (Optional[str]): The template of the email sequence
        sequence_delay_days (Optional[int]): The number of days to delay the email sequence
        bumped_count (Optional[int], optional): The number which corresponds to which bump in the sequence this step appears. Defaults to None.
        default (Optional[bool]): Whether the email sequence is the default
        transformer_blocklist (Optional[list], optional): The blocklist of transformer types. Defaults to [].

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

    if sequence_delay_days and sequence_delay_days > 0:
        sequence_step.sequence_delay_days = sequence_delay_days

    sequence_step.transformer_blocklist = transformer_blocklist

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


def undefault_all_sequence_steps_in_status(
    client_sdr_id: int,
    sequence_step_id: int
) -> bool:
    """Marks all sequence steps in the same status as the given sequence step as no longer default

    Args:
        client_sdr_id (int): The id of the client SDR
        sequence_step_id (int): The id of the sequence step

    Returns:
        bool: Whether the sequence steps were deactivated
    """
    sequence_step: EmailSequenceStep = EmailSequenceStep.query.filter(
        EmailSequenceStep.client_sdr_id == client_sdr_id,
        EmailSequenceStep.id == sequence_step_id,
    ).first()
    if not sequence_step:
        return False

    sequence_step.default = False

    # Get sequence steps in the same status
    sequence_steps: list[EmailSequenceStep] = EmailSequenceStep.query.filter(
        EmailSequenceStep.client_sdr_id == client_sdr_id,
        EmailSequenceStep.client_archetype_id == sequence_step.client_archetype_id,
        EmailSequenceStep.overall_status == sequence_step.overall_status,
        EmailSequenceStep.substatus == sequence_step.substatus,
        EmailSequenceStep.bumped_count == sequence_step.bumped_count,
    ).all()
    for sequence_step in sequence_steps:
        sequence_step.default = False

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

    templates: list[EmailSubjectLineTemplate] = templates.order_by(
        EmailSubjectLineTemplate.active.desc(),
    ).all()

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
    subject_line: Optional[str] = None,
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


def create_email_template_pool_item(
    name: str,
    template: str,
    template_type: EmailTemplateType,
    description: Optional[str] = "",
    transformer_blocklist: Optional[list[ResearchPointType]] = [],
    labels: Optional[list[str]] = [],
    tone: Optional[str] = "",
    active: bool = True,
) -> tuple[bool, int]:
    """Create a new email template pool item

    Args:
        name (str): The name of the email template pool item
        template (str): The template of the email template pool item
        template_type (EmailTemplateType): The type of the email template pool item
        description (Optional[str], optional): The description of the email template pool item. Defaults to "".
        transformer_blocklist (Optional[list[ResearchPointType]], optional): The blocklist of transformer types. Defaults to [].
        labels (Optional[list[str]], optional): The labels of the email template pool item. Defaults to [].
        tone (Optional[str], optional): The tone of the email template pool item. Defaults to "".
        active (bool, optional): Whether the email template pool item is active. Defaults to True.

    Returns:
        tuple[bool, int]: Whether the email template pool item was created and the id of the newly created email template pool item
    """
    # Create the email template pool item
    template = EmailTemplatePool(
        name=name,
        description=description,
        template=template,
        template_type=template_type,
        active=active,
        transformer_blocklist=transformer_blocklist,
        labels=labels,
        tone=tone,
    )
    db.session.add(template)
    db.session.commit

    return True, template.id


def modify_email_template_pool_item(
    email_template_pool_item_id: int,
    name: Optional[str] = None,
    template: Optional[str] = None,
    description: Optional[str] = None,
    transformer_blocklist: Optional[list[ResearchPointType]] = None,
    labels: Optional[list[str]] = None,
    tone: Optional[str] = None,
    active: Optional[bool] = None,
) -> bool:
    """Modify a email template pool item

    Args:
        email_template_pool_item_id (int): The id of the email template pool item
        name (Optional[str]): The name of the email template pool item
        template (Optional[str]): The template of the email template pool item
        template_type (Optional[EmailTemplateType]): The type of the email template pool item
        description (Optional[str], optional): The description of the email template pool item. Defaults to "".
        transformer_blocklist (Optional[list[ResearchPointType]], optional): The blocklist of transformer types. Defaults to [].
        labels (Optional[list[str]], optional): The labels of the email template pool item. Defaults to [].
        tone (Optional[str], optional): The tone of the email template pool item. Defaults to "".
        active (Optional[bool], optional): Whether the email template pool item is active. Defaults to True.

    Returns:
        bool: Whether the email template pool item was modified
    """
    template: EmailTemplatePool = EmailTemplatePool.query.filter(
        EmailTemplatePool.id == email_template_pool_item_id,
    ).first()
    if not template:
        return False

    template.name = name
    template.template = template
    template.description = description
    template.transformer_blocklist = transformer_blocklist
    template.labels = labels
    template.tone = tone
    template.active = active

    db.session.add(template)
    db.session.commit()

    return True
