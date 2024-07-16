import datetime
import json
import re

from model_import import (
    EmailSequenceStep,
    EmailSubjectLineTemplate,
)
from app import db
from src.client.models import ClientArchetype, ClientAssets, ClientSDR, Client
from src.email_outbound.models import ProspectEmail
from src.email_sequencing.models import (
    EmailGraderEntry,
    EmailSequenceStepToAssetMapping,
    EmailTemplatePool,
    EmailTemplateType,
)
import yaml
from src.ml.models import LLM, LLMModel
from src.ml.services import get_text_generation
from src.prospecting.models import Prospect, ProspectOverallStatus, ProspectStatus
from typing import List, Optional, Union
from src.ml.openai_wrappers import (
    streamed_chat_completion_to_socket,
)
from src.ml.spam_detection import run_algorithmic_spam_detection


from src.smartlead.services import sync_smartlead_send_schedule
from src.utils.slack import URL_MAP, send_slack_message


def get_email_sequence_step_for_sdr(
    client_sdr_id: int,
    overall_statuses: Optional[list[ProspectOverallStatus]] = [],
    substatuses: Optional[list[str]] = [],
    client_archetype_ids: Optional[list[int]] = [],
    activeOnly: Optional[bool] = False,
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

    # steps: list[EmailSequenceStep] = EmailSequenceStep.query.filter(
    #     EmailSequenceStep.client_sdr_id == client_sdr_id,
    #     EmailSequenceStep.client_archetype_id.in_(client_archetype_ids),
    #     EmailSequenceStep.overall_status.in_(overall_statuses),
    # )

    sequence_steps_with_assets = (
        db.session.query(EmailSequenceStep, ClientAssets)
        .outerjoin(
            EmailSequenceStepToAssetMapping,
            EmailSequenceStepToAssetMapping.email_sequence_step_id
            == EmailSequenceStep.id,
        )
        .outerjoin(
            ClientAssets,
            EmailSequenceStepToAssetMapping.client_assets_id == ClientAssets.id,
        )
        .filter(
            EmailSequenceStep.client_sdr_id == client_sdr_id,
            EmailSequenceStep.client_archetype_id.in_(client_archetype_ids),
            EmailSequenceStep.overall_status.in_(overall_statuses),
        )
    )

    # mappings: list[
    #     EmailSequenceStepToAssetMapping
    # ] = EmailSequenceStepToAssetMapping.query.filter(
    #     EmailSequenceStepToAssetMapping.email_sequence_step_id == email_sequence_step_id
    # ).all()
    # asset_ids = [mapping.client_assets_id for mapping in mappings]
    # assets: ClientAssets = ClientAssets.query.filter(
    #     ClientAssets.id.in_(asset_ids)
    # ).all()
    # asset_dicts = [asset.to_dict() for asset in assets]

    # If substatuses is specified, filter by substatuses
    if len(substatuses) > 0:
        sequence_steps_with_assets = sequence_steps_with_assets.filter(
            EmailSequenceStep.substatus.in_(substatuses)
        )

    # If activeOnly is specified, filter by active
    if activeOnly:
        sequence_steps_with_assets = sequence_steps_with_assets.filter(
            EmailSequenceStep.active == True,
        )

    sequence_steps_with_assets = sequence_steps_with_assets.all()

    # Organize the results into a structure that maps sequence steps to their assets
    from collections import defaultdict

    sequence_to_assets = defaultdict(list)
    for step, asset in sequence_steps_with_assets:
        # Here, asset could be None if the step has no associated assets
        if asset:  # Only append if asset is not None
            sequence_to_assets[step].append(asset)
        else:  # Ensure the step is included even if it has no assets
            sequence_to_assets[step]

    # To create a more structured output
    sequence_to_assets_list = [
        {
            "step": step.to_dict(),
            "assets": (
                [asset.to_dict() for asset in assets] if assets else []
            ),  # Handle steps with no assets
        }
        for step, assets in sequence_to_assets.items()
    ]

    return sequence_to_assets_list


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
    for step_data in sequence_steps:
        if step_data.get("step").get("overall_status") in counts:
            counts[step_data.get("step").get("overall_status")] += 1
        if step_data.get("step").get("substatus") in counts:
            counts[step_data.get("step").get("substatus")] += 1

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
    default: Optional[bool] = False,  # DEPRECATED
    sellscale_default_generated: Optional[bool] = False,
    transformer_blocklist: Optional[list] = [],
    sequence_delay_days: Optional[int] = 3,
    mapped_asset_ids: Optional[list[int]] = [],
) -> tuple[Union[int, None], str]:
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
        DEPRECATED: default (Optional[bool], optional): Whether the email sequence is the default. Defaults to False.
        sellscale_default_generated (Optional[bool], optional): Whether the email sequence was generated by SellScale. Defaults to False.
        transformer_blocklist (Optional[list], optional): The blocklist of transformer types. Defaults to [].
        sequence_delay_days (Optional[int], optional): The number of days to delay the email sequence. Defaults to 3.
        mapped_asset_ids (Optional[list[int]], optional): The ids of the assets to map to the email sequence. Defaults to [].

    Returns:
        int: The id of the newly created email sequence
    """
    archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.id == client_archetype_id,
    ).first()
    if not archetype:
        return None, "Client archetype not found"
    if (
        archetype.smartlead_campaign_id
    ):  # Block if the archetype has a smartlead campaign synced (not allowed to create)
        # EDGE CASE: We allow the creation of additional templates IFF one already exists for that step
        # i.e. The user can create a new "variant" for the same step, but can't create a new step (inferred through bump count)
        existing_sequence_steps: list[EmailSequenceStep] = (
            EmailSequenceStep.query.filter(
                EmailSequenceStep.client_sdr_id == client_sdr_id,
                EmailSequenceStep.client_archetype_id == client_archetype_id,
                EmailSequenceStep.overall_status == overall_status,
                EmailSequenceStep.bumped_count == bumped_count,
            )
        ).all()
        if not existing_sequence_steps:
            return (
                None,
                "Campaign already outbounding, you cannot add additional steps. Variants are allowed.",
            )

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
        sequence_delay_days=sequence_delay_days,
    )
    db.session.add(sequence_step)
    db.session.commit()
    sequence_step_id = sequence_step.id

    if mapped_asset_ids and len(mapped_asset_ids) > 0:
        for asset_id in mapped_asset_ids:
            try:
                create_email_sequence_step_asset_mapping(
                    email_sequence_step_id=sequence_step_id,
                    client_assets_id=asset_id,
                )
            except:
                db.session.rollback()
                pass

    return sequence_step_id, ""


def modify_email_sequence_step(
    client_sdr_id: int,
    client_archetype_id: int,
    sequence_step_id: int,
    title: Optional[str] = None,
    template: Optional[str] = None,
    sequence_delay_days: Optional[int] = None,
    bumped_count: Optional[int] = None,
    default: Optional[bool] = False,  # Deprecated
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

    # if default:
    #     default_sequence_steps: list[EmailSequenceStep] = (
    #         EmailSequenceStep.query.filter(
    #             EmailSequenceStep.client_sdr_id == client_sdr_id,
    #             EmailSequenceStep.client_archetype_id == client_archetype_id,
    #             EmailSequenceStep.overall_status == overall_status,
    #             EmailSequenceStep.default == True,
    #         )
    #     )
    #     if substatus:
    #         default_sequence_steps = default_sequence_steps.filter(
    #             EmailSequenceStep.substatus == substatus
    #         )

    #     if overall_status == ProspectOverallStatus.BUMPED and bumped_count is not None:
    #         default_sequence_steps = default_sequence_steps.filter(
    #             EmailSequenceStep.bumped_count == bumped_count
    #         )
    #     default_sequence_steps = default_sequence_steps.all()
    #     for default_sequence_step in default_sequence_steps:
    #         default_sequence_step.default = False
    #         db.session.add(default_sequence_step)
    # sequence_step.default = default

    db.session.add(sequence_step)
    db.session.commit()

    # Aakash commented this out because it was messing up the smartlead campaign analytics and zeroing out the stats
    # success, message = sync_smartlead_send_schedule(
    #     archetype_id=client_archetype_id,
    # )

    return True


# DEPRECATED
def undefault_all_sequence_steps_in_status(
    client_sdr_id: int, sequence_step_id: int
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

    archetype: ClientArchetype = ClientArchetype.query.filter(
        ClientArchetype.id == sequence_step.client_archetype_id,
    ).first()
    if not archetype:
        return False
    if (
        archetype.smartlead_campaign_id
    ):  # Block if the archetype has a smartlead campaign synced (not allowed to create)
        return False

    sequence_step.default = False
    sequence_step.active = False

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
        sequence_step.active = False

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

def generate_email_subject_lines(client_sdr_id, archetype_id) -> list[str]:
    """Generates email subject lines based on the given archetype ID and associated body templates

    Args:
        archetype_id (int): The id of the archetype

    Returns:
        list[str]: A list of generated email subject lines
    """
    if not archetype_id:
        return []
    
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)

    if not archetype:
        return []

    # Get existing email body templates for the client archetype
    email_templates: list[EmailSequenceStep] = EmailSequenceStep.query.filter(
        EmailSequenceStep.client_archetype_id == archetype_id,
        EmailSequenceStep.active == True
    ).all()

    if not email_templates:
        return []

    client_description = client.description
    company_name = client.company

    # Combine the body templates into a single string
    body_content = " ".join([template.template for template in email_templates])

    llm = LLM(
        name="generate_email_subject_lines",
        dependencies={
            "company_name": company_name,
            "client_description": client_description,
            "body_content": body_content
        }
    )

    def generate_subject_lines_with_retry(llm, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = llm()
                start_idx = response.find('[')
                end_idx = response.rfind(']') + 1
                if start_idx != -1 and end_idx != -1:
                    response = response[start_idx:end_idx]
                
                result = json.loads(response)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError as e:
                print(f"JSON decode error generating email subject lines (Attempt {attempt + 1}): {e}")
            except Exception as e:
                print(f"Error generating email subject lines (Attempt {attempt + 1}): {e}")
        return []

    subject_lines = generate_subject_lines_with_retry(llm)
    created_subject_lines = []
    for subject_line in subject_lines:
        template_id = create_email_subject_line_template(
            client_sdr_id=client_sdr_id,
            client_archetype_id=archetype_id,
            subject_line=subject_line,
            active=True,
            sellscale_generated=True,
        )
        template = EmailSubjectLineTemplate.query.get(template_id)
        created_subject_lines.append(template.to_dict())
    return created_subject_lines

def create_email_subject_line_template(
    client_sdr_id: int,
    client_archetype_id: int,
    subject_line: str,
    active: bool = True,
    sellscale_generated: bool = False,
    is_magic_subject_line: Optional[bool] = False,
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
        is_magic_subject_line=is_magic_subject_line,
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
        if len(subject_line) > 100:
            return False

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


def get_email_template_pool_items(
    template_type: Optional[EmailTemplateType] = None,
    active_only: Optional[bool] = True,
) -> list[EmailTemplatePool]:
    """Gets all email template pool items

    Args:
        template_type (Optional[EmailTemplateType], optional): The type of the email template pool item. Defaults to None.
        active_only (Optional[bool], optional): Whether to only return active email template pool items. Defaults to True.

    Returns:
        list[EmailTemplatePool]: A list of email template pool items
    """
    templates: list[EmailTemplatePool] = EmailTemplatePool.query

    # If template_type is specified, filter by template_type
    if template_type:
        templates = templates.filter(EmailTemplatePool.template_type == template_type)

    # If activeOnly is specified, filter by active
    if active_only:
        templates = templates.filter(EmailTemplatePool.active == True)

    templates: list[EmailTemplatePool] = templates.order_by(
        EmailTemplatePool.id.asc(),
    ).all()

    return templates


def create_email_template_pool_item(
    name: str,
    template: str,
    template_type: EmailTemplateType,
    description: Optional[str] = "",
    transformer_blocklist: Optional[list[str]] = [],
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
        transformer_blocklist (Optional[list[str]], optional): The blocklist of transformer types. Defaults to [].
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
    db.session.commit()

    return True, template.id


def modify_email_template_pool_item(
    email_template_pool_item_id: int,
    name: Optional[str] = None,
    template: Optional[str] = None,
    description: Optional[str] = None,
    transformer_blocklist: Optional[list[str]] = None,
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
        transformer_blocklist (Optional[list[str]], optional): The blocklist of transformer types. Defaults to [].
        labels (Optional[list[str]], optional): The labels of the email template pool item. Defaults to [].
        tone (Optional[str], optional): The tone of the email template pool item. Defaults to "".
        active (Optional[bool], optional): Whether the email template pool item is active. Defaults to True.

    Returns:
        bool: Whether the email template pool item was modified
    """
    template_entry: EmailTemplatePool = EmailTemplatePool.query.filter(
        EmailTemplatePool.id == email_template_pool_item_id,
    ).first()
    if not template_entry:
        return False

    template_entry.name = name
    template_entry.template = template
    template_entry.description = description
    template_entry.transformer_blocklist = transformer_blocklist
    template_entry.labels = labels
    template_entry.tone = tone
    template_entry.active = active

    db.session.add(template_entry)
    db.session.commit()

    return True


def copy_email_template_subject_line_item(
    client_sdr_id: int,
    client_archetype_id: int,
    template_pool_id: int,
) -> bool:
    """Copies an email template pool item to the email subject line template table

    Args:
        client_sdr_id (int): The id of the SDR
        client_archetype_id (int): The id of the archetype
        template_pool_id (int): The id of the email template pool item

    Returns:
        bool: Whether the email template pool item was copied
    """
    template_pool_item: EmailTemplatePool = EmailTemplatePool.query.filter(
        EmailTemplatePool.id == template_pool_id,
    ).first()
    if (
        not template_pool_item
        or template_pool_item.template_type != EmailTemplateType.SUBJECT_LINE
    ):
        return False

    # Create the email subject line template
    template = EmailSubjectLineTemplate(
        subject_line=template_pool_item.template,
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        active=True,
    )
    db.session.add(template)
    db.session.commit()

    return True


def copy_email_template_body_item(
    client_sdr_id: int,
    client_archetype_id: int,
    template_pool_id: int,
    overall_status: ProspectOverallStatus,
    substatus: Optional[str] = None,
    bumped_count: Optional[int] = None,
    transformer_blocklist: Optional[list[str]] = [],
) -> bool:
    """Copies an email template pool item to the email sequence step table

    Args:
        client_sdr_id (int): The id of the SDR
        client_archetype_id (int): The id of the archetype
        template_pool_id (int): The id of the email template pool item
        overall_status (ProspectOverallStatus): The overall status of the email sequence step
        substatus (Optional[str], optional): The substatus of the email sequence step. Defaults to None.
        bumped_count (Optional[int], optional): The number which corresponds to which bump in the sequence this step appears. Defaults to None.
        transformer_blocklist (Optional[list[str]], optional): The blocklist of transformer types. Defaults to [].

    Returns:
        bool: Whether the email template pool item was copied
    """
    template_pool_item: EmailTemplatePool = EmailTemplatePool.query.filter(
        EmailTemplatePool.id == template_pool_id,
    ).first()
    if (
        not template_pool_item
        or template_pool_item.template_type != EmailTemplateType.BODY
    ):
        return False

    # Create the email sequence step
    id, message = create_email_sequence_step(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        title=template_pool_item.name,
        template=template_pool_item.template,
        overall_status=overall_status,
        substatus=substatus,
        bumped_count=bumped_count,
        # default=True,
        transformer_blocklist=transformer_blocklist,
    )

    return True


def grade_email(tracking_data: dict, subject: str, body: str):
    # Detect spam words
    spam_subject_results = run_algorithmic_spam_detection(subject)
    spam_subject_words = spam_subject_results.get("spam_words") or []

    spam_body_results = run_algorithmic_spam_detection(body)
    spam_body_words = spam_body_results.get("spam_words") or []

    # Evaluate subject line and body construction
    subject_line_good = len(subject) < 100
    body_good = len(body.split()) > 50 and len(body.split()) < 120
    read_time = int(len(body.split()) / 4)

    # Detect tones and personalizations
    tones = detect_tones(subject, body)
    personalizations = detect_personalizations(subject, body)

    feedback = generate_email_feedback(subject=subject, body=body)

    grevious_error = identify_any_grevious_errors(subject=subject, body=body)

    # Calculate feedback score
    goods = sum(
        [
            subject_line_good,
            body_good,
            read_time <= 30,
            len(spam_subject_words) == 0,
            len(spam_body_words) == 0,
        ]
    )

    # Get value from 0 - 1, based on the number of pros in the feedback
    feedback_point = sum(
        [0.5 if feedback_item.get("type") == "pro" else 0 for feedback_item in feedback]
    ) / len(feedback)
    goods += feedback_point

    total_checks = 5 + (len(feedback) / 2)
    feedback_score = int((goods / total_checks) * 100)

    # Make alterations to score based on heuristics
    if len(body.split()) < 30:
        feedback_score = feedback_score * 0.35
    if sum(feedback_item.get("type") == "delta" for feedback_item in feedback) > (
        len(feedback) / 2
    ):
        feedback_score = feedback_score * 0.5
    if grevious_error and "true" in grevious_error.lower():
        feedback_score = feedback_score * 0.1
    if len(spam_subject_words) > 0:
        feedback_score = feedback_score * 0.75
    if len(spam_body_words) > 0:
        feedback_score = feedback_score * 0.75
    if sum(
        personalization.get("strength") == "strong"
        for personalization in personalizations
    ) > (len(personalizations) / 3):
        feedback_score *= 1.15

    if feedback_score > 50:
        feedback_score *= 1.1

    # Cap the score at 100 and floor at 0
    if feedback_score > 100:
        feedback_score = 100
    if feedback_score < 0:
        feedback_score = 0

    # Create a record in the database
    entry = EmailGraderEntry(
        input_tracking_data=tracking_data,
        input_subject_line=subject,
        input_body=body,
        detected_company=detect_company(subject, body),
        evaluated_score=feedback_score,
        evaluated_feedback=feedback,
        evaluated_tones={"tones": tones},
        evaluated_construction_subject_line="GOOD" if subject_line_good else "BAD",
        evaluated_construction_spam_words_subject_line={
            "words": spam_subject_words,
            "evaluation": "GOOD" if len(spam_subject_words) == 0 else "BAD",
        },
        evaluated_construction_body="GOOD" if body_good else "BAD",
        evaluated_construction_spam_words_body={
            "words": spam_body_words,
            "evaluation": "GOOD" if len(spam_body_words) == 0 else "BAD",
        },
        evaluated_read_time_seconds=read_time,
        evaluated_personalizations=personalizations,
    )
    db.session.add(entry)
    db.session.commit()

    # replace all <p> with \n
    sanitized_body = re.sub(r"<p>", "\n", body)
    sanitized_body = re.sub(r"</p>", "", sanitized_body)

    feedback_score_rounded = round(feedback_score, 2)

    send_slack_message(
        message="🍯📧 New Email Grader Submission!",
        webhook_urls=[URL_MAP["honeypot-email-grader"]],
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🍯📧 New Email Grader Submission!",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""
*Score:* {feedback_score_rounded}%
                    """,
                },
            },
            {
                "type": "divider",
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""
*Spam Words in Subject Line:* {spam_subject_words}
*Spam Words in Body:* {spam_body_words}
*Read Time:* {read_time} seconds
                    """,
                },
            },
            {
                "type": "divider",
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""
*Subject Line:*
{subject}

*Email:*
{sanitized_body}
                    """,
                },
            },
        ],
    )

    return entry.id, entry.to_dict()


def detect_tones(subject: str, text: str) -> dict:
    """Detects the tones of the text

    Args:
        text (str): The text to detect the tones of

    Returns:
        dict: The tones of the text
    """

    completion = streamed_chat_completion_to_socket(
        event="generate_email_feedback",
        room_id=subject,
        messages=[
            {
                "role": "user",
                "content": f"""
                Given the following text, return only 3-6 adjectives that describe the tone of the text. Return these as a JSON array of strings.

                ### Text:
                {text}

                """,
            }
        ],
        model="gpt-4",
        max_tokens=120,
    )

    try:
        return yaml.safe_load(completion)
    except:
        return []


def detect_company(subject: str, text: str) -> dict:
    """Detects the company name

    Args:
        text (str): The email body

    Returns:
        The company name (str) or None
    """

    completion = streamed_chat_completion_to_socket(
        event="generate_email_feedback",
        room_id=subject,
        messages=[
            {
                "role": "user",
                "content": f"""
                Given the following email body, please return the assumed name of the company that's sending out the email. Only respond with the company name. If you have no idea, return with "Unknown"

                ### Email Body:
                {text}

                """,
            }
        ],
        model="gpt-4",
        max_tokens=40,
    )

    if completion.lower().strip() == "unknown":
        return None
    else:
        return completion


def detect_personalizations(subject: str, text: str) -> dict:
    """Detects the personalizations of the text

    Args:
        text (str): The text to detect the personalizations of

    Returns:
        dict: The personalizations of the text
    """

    completion = streamed_chat_completion_to_socket(
        event="generate_email_feedback",
        room_id=subject,
        messages=[
            {
                "role": "user",
                "content": f"""
          You are going to extract 'personalization key points' from the email copy I provide.

I want a list of JSON objects outputted:
`personalization` - Extract small phrases or snippets from the email that are personalization
`strength` - 'weak' or 'strong'
`reason` - Explain why the personalization is weak or strong

IMPORTANT: Only respond with the output in a JSON list.

Here are two examples of email copy and the output I wanted.

-----------------
Copy: ""
Hey Sarah,

As you're considering how to streamline CHAS Health's operations, it would be worth to consider SuperBill. It can integrate with your existing call process - credentialing, follow-ups, verification - and give time back to staff.

For example, verifying a new patient's insurance. In SuperBill, you simply input the patient's details and our AI instantly handles the calls to insurance providers, freeing up your staff's time and energy. Works for your local and nationwide insurers, too.

If you're open to it, I'd love to show you how it works. Any interest?

Sam Schwager, CEO at SuperBill

P.S. If there's no interest, please let me know and I'll stop reaching out.
""
Output:
[
{{"personalization": "CHAS Health's Operations", "strength": "weak", "reason": "Company name is something that can be easily 'copy-pasted' via a sequencing tool."}},
]
""

-----------------
copy: ""
Hi Carlos,

Happy belated 5-year anniversary at Mondi! Your expertise in supply chain management and circular economy is truly impressive, especially with your multilingual skills in Spanish, English, German, and Italian.

I'm reaching out to you today in hopes of fostering some cross-industry discussion to solve one of the world's toughest sustainability challenges – enhancing plastics circularity. My company, Worley, has been developing a solution that would verify and track recycled content in plastics in a more granular way than was previously thought possible. As someone who is deeply invested in meeting the sustainable packaging needs of top brand owners, I'd love to get your insights on this very important topic.

Could we schedule virtual meeting in the next few weeks for a quick chat?

Best Regards,

Jennifer Lee

Vice President, Plastics Recycling - Worley
""

Output:
[
{{"personalization": "belated 5-year anniversary at Mondi", "strength": "strong", "reason": "Anniversaries on the job are highly time-based and relevant. Good personalization!"}},
{{"personalization": "expertise in supply chain...", "strength": "strong", "reason": "You are identifying why their expertise is relevant to what we are reaching out for"}},
{{"personalization": "Spanish, English, German...", "strength": "weak", "reason": "Their multilingual abilities are not quite relevant to what we are reaching out for tracking recycled content"}},
]

-----------------
copy: ""
{text}
""
output:
          """,
            }
        ],
        model="gpt-4",
        max_tokens=1024,
    )

    try:
        return yaml.safe_load(completion)
    except:
        return []


def generate_email_feedback(subject: str, body: str) -> dict:
    completion = streamed_chat_completion_to_socket(
        event="generate_email_feedback",
        room_id=subject,
        messages=[
            {
                "role": "user",
                "content": f"""
You are going to extract 'feedback' from the email copy I provide.

Here are two examples of email copy and the output I wanted.

-----------------
Copy: ""
subject: Transform CHAS Health's Efficiency
Hey Sarah,

As you're considering how to streamline CHAS Health's operations, it would be worth to consider SuperBill. It can integrate with your existing call process - credentialing, follow-ups, verification - and give time back to staff.

For example, verifying a new patient's insurance. In SuperBill, you simply input the patient's details and our AI instantly handles the calls to insurance providers, freeing up your staff's time and energy. Works for your local and nationwide insurers, too.

If you're open to it, I'd love to show you how it works. Any interest?

Sam Schwager, CEO at SuperBill

P.S. If there's no interest, please let me know and I'll stop reaching out.
""
Output:
[
{{"feedback": "There is quite a lot of 'us' related content in this email. For example, we mentioned Superbill, our features, 'our AI', etc. We need to focus more on their product or service in the email.", "type": "delta"}},
{{"feedback": "There is a lack of personalization. We should for example include information about Sarah's role, her company, and how they may be considering dials due to a recent event.", "type": "delta"}},
{{"feedback": "It's good that you included a soft opt-out at the end of the email. This may increase reply rates", "type": "pro"}}
]
""

-----------------
Copy: ""
subject: Enhancing Plastics Circularity: Seeking Your Insights, Carlos
Hi Carlos,

Happy belated 5-year anniversary at Mondi! Your expertise in supply chain management and circular economy is truly impressive, especially with your multilingual skills in Spanish, English, German, and Italian.

I'm reaching out to you today in hopes of fostering some cross-industry discussion to solve one of the world's toughest sustainability challenges – enhancing plastics circularity. My company, Worley, has been developing a solution that would verify and track recycled content in plastics in a more granular way than was previously thought possible. As someone who is deeply invested in meeting the sustainable packaging needs of top brand owners, I'd love to get your insights on this very important topic.

Could we schedule virtual meeting in the next few weeks for a quick chat?

Best Regards,

Jennifer Lee

Vice President, Plastics Recycling - Worley
""

Output:
[
{{"feedback": "It's great that you called out the prospect's recent anniversary and expertise areas. This kind of personalization, in the first line of the email, increases conversion rates drastically.", "type": "pro"}},
{{"feedback": "Mention their multilingual abilities is a bit strange because of the context of this email. It may be better to personalize using something relevant to their role or company instead.", "type": "delta"}},
{{"feedback": "The entire second paragraph is about Worley and Worley's offering - which is an 'us' or 'me' statement. It would instead be better to target the prospect's company and embed how Worley can help solve specific issues they may be encountering."}}
]

-----------------
Copy: ""
subject: {subject}
{body}
""
Output:
                """,
            }
        ],
        model="gpt-4",
        max_tokens=1024,
    )

    try:
        return yaml.safe_load(completion)
    except:
        return []


def identify_any_grevious_errors(subject: str, body: str) -> str:
    completion = streamed_chat_completion_to_socket(
        event="generate_email_feedback",
        room_id=subject,
        messages=[
            {
                "role": "user",
                "content": f"""
You are going to extract 'feedback' from the email copy I provide.

Here are two examples of email copy and the output I wanted.

-----------------
Copy: ""
subject: Transform CHAS Health's Efficiency
Hey Sarah,

As you're considering how to streamline CHAS Health's operations, it would be worth to consider SuperBill. It can integrate with your existing call process - credentialing, follow-ups, verification - and give time back to staff.

For example, verifying a new patient's insurance. In SuperBill, you simply input the patient's details and our AI instantly handles the calls to insurance providers, freeing up your staff's time and energy. Works for your local and nationwide insurers, too.

If you're open to it, I'd love to show you how it works. Any interest?

Sam Schwager, CEO at SuperBill

P.S. If there's no interest, please let me know and I'll stop reaching out.
""
Output:
FALSE
""

-----------------
Copy: ""
subject: Enhancing Plastics Circularity: Seeking Your Insights, Carlos
Hi Carlos,

Happy belated 5-year anniversary at Mondi! Your expertise in supply chain management and circular economy is truly impressive, especially with your multilingual skills in Spanish, English, German, and Italian.

I'm reaching out to you today in hopes of fostering some cross-industry discussion to solve one of the world's toughest sustainability challenges – enhancing plastics circularity. My company, Worley, has been developing a solution that would verify and track recycled content in plastics in a more granular way than was previously thought possible. As someone who is deeply invested in meeting the sustainable packaging needs of top brand owners, I'd love to get your insights on this very important topic.

Could we schedule virtual meeting in the next few weeks for a quick chat?

Best Regards,

Jennifer Lee

Vice President, Plastics Recycling - Worley

PS. SCREW YOU MAN!
""

Output:
TRUE

-----------------
Copy: ""
subject: {subject}
{body}
""

Instruction: Based on the email provided, identify if there's any grevious errors. Grevious errors include cuss words, insults, harmful language, etc.
If grevious error identified, output TRUE. Otherwise, output FALSE.

Output:""",
            }
        ],
        model="gpt-4",
        max_tokens=1024,
    )

    try:
        return completion
    except:
        return "FALSE"


def create_email_sequence_step_asset_mapping(
    email_sequence_step_id: int, client_assets_id: int
):
    mapping: EmailSequenceStepToAssetMapping = EmailSequenceStepToAssetMapping(
        email_sequence_step_id=email_sequence_step_id,
        client_assets_id=client_assets_id,
    )
    db.session.add(mapping)
    db.session.commit()
    return True


def delete_email_sequence_step_asset_mapping(
    email_sequence_step_to_asset_mapping_id: int,
):
    mapping: EmailSequenceStepToAssetMapping = (
        EmailSequenceStepToAssetMapping.query.get(
            email_sequence_step_to_asset_mapping_id
        )
    )
    if not mapping:
        return True

    db.session.delete(mapping)
    db.session.commit()
    return True


def get_all_email_sequence_step_assets(email_sequence_step_id: int):
    mappings: list[
        EmailSequenceStepToAssetMapping
    ] = EmailSequenceStepToAssetMapping.query.filter(
        EmailSequenceStepToAssetMapping.email_sequence_step_id == email_sequence_step_id
    ).all()
    asset_ids = [mapping.client_assets_id for mapping in mappings]
    assets: ClientAssets = ClientAssets.query.filter(
        ClientAssets.id.in_(asset_ids)
    ).all()
    asset_dicts = [asset.to_dict() for asset in assets]

    # add 'mapping_id' to each asset
    for i, asset in enumerate(asset_dicts):
        correct_mapping = next(
            mapping for mapping in mappings if mapping.client_assets_id == asset["id"]
        )
        asset["mapping_id"] = correct_mapping.id

    return asset_dicts
