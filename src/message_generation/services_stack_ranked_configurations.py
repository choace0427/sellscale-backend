from src.prospecting.models import ProspectOverallStatus
from model_import import (
    StackRankedMessageGenerationConfiguration,
    ResearchPointType,
    ConfigurationType,
    GeneratedMessage,
    Client,
    ClientArchetype,
    ResearchPoints,
)
from sqlalchemy import or_, and_, text
from sqlalchemy.orm import attributes
from typing import Optional
from app import db
import random
from sqlalchemy.sql.expression import func
from sqlalchemy.dialects.postgresql import ARRAY
from src.client.models import ClientSDR
from src.ml.fine_tuned_models import get_computed_prompt_completion
from src.prospecting.models import Prospect

from src.research.linkedin.services import get_research_and_bullet_points_new


def compute_prompt(stack_ranked_configuration_id: int):
    """Compute the prompt for a stack ranked message generation configuration"""
    pass


def create_stack_ranked_configuration(
    configuration_type: str,
    research_point_types: list[ResearchPointType],
    instruction: str,
    generated_message_type: str,
    name: Optional[str] = None,
    client_id: Optional[int] = None,
    archetype_id: Optional[int] = None,
) -> tuple[bool, str]:
    """Create a new stack ranked message generation configuration"""
    client_name = "All Clients"
    archetype_name = "All Archetypes"
    if client_id:
        client: Client = Client.query.filter_by(id=client_id).first()
        client_name = client.company
        if not client:
            return False, "Client does not exist"
    if archetype_id:
        archetype: ClientArchetype = ClientArchetype.query.filter_by(
            id=archetype_id
        ).first()
        archetype_name = archetype.archetype
        if not archetype:
            return False, "Archetype does not exist"

    research_point_types_values_str = ", ".join(
        [research_point_type.value for research_point_type in research_point_types]
    )
    if not name:
        name = f"{client_name} {archetype_name} - {configuration_type} - {research_point_types_values_str}"

    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration(
            configuration_type=configuration_type,
            research_point_types=research_point_types,
            instruction=instruction,
            computed_prompt="",
            name=name,
            client_id=client_id,
            archetype_id=archetype_id,
            generated_message_type=generated_message_type,
        )
    )
    db.session.add(srmgc)
    db.session.commit()
    srmgc_id = srmgc.id

    compute_prompt(srmgc_id)

    return True, "OK"


def edit_stack_ranked_configuration_instruction(
    stack_ranked_configuration_id: int,
    instruction: str,
) -> tuple[bool, str]:
    """Edit the instruction of a stack ranked message generation configuration"""
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=stack_ranked_configuration_id
        ).first()
    )
    if not srmgc:
        return False, "Stack ranked message generation configuration does not exist"
    srmgc.instruction = instruction
    db.session.add(srmgc)
    db.session.commit()
    return True, "OK"


def edit_stack_ranked_configuration_research_point_types(
    stack_ranked_configuration_id: int,
    research_point_types: list[ResearchPointType],
):
    """Edit the research point types of a stack ranked message generation configuration"""
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=stack_ranked_configuration_id
        ).first()
    )
    if not srmgc:
        return False, "Stack ranked message generation configuration does not exist"
    srmgc.research_point_types = research_point_types
    db.session.add(srmgc)
    db.session.commit()
    return True, "OK"


def edit_stack_ranked_configuration_name(
    stack_ranked_configuration_id: int,
    name: str,
):
    """Edit the name of a stack ranked message generation configuration"""
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=stack_ranked_configuration_id
        ).first()
    )
    if not srmgc:
        return False, "Stack ranked message generation configuration does not exist"
    srmgc.name = name
    db.session.add(srmgc)
    db.session.commit()
    return True, "OK"


def delete_stack_ranked_configuration(
    stack_ranked_configuration_id: int,
) -> tuple[bool, str]:
    """Delete a stack ranked message generation configuration"""
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=stack_ranked_configuration_id
        ).first()
    )
    if not srmgc:
        return False, "Stack ranked message generation configuration does not exist"
    db.session.delete(srmgc)
    db.session.commit()
    return True, "OK"


def get_top_stack_ranked_config_ordering(
    generated_message_type: str, prospect_id: int, discluded_config_ids: list[int] = []
):
    """Get the top stack ranked message generation configuration ordering for a client archetype"""
    from model_import import Prospect

    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    client_id = prospect.client_id
    archetype_id = prospect.archetype_id
    stack_ranked_config_ordering: list = get_stack_ranked_config_ordering(
        generated_message_type=generated_message_type,
        archetype_id=archetype_id,
        client_id=client_id,
        prospect_id=prospect_id,
        only_active_configs=True,
        discluded_config_ids=discluded_config_ids,
    )
    if len(stack_ranked_config_ordering) > 0:
        return random.choice(stack_ranked_config_ordering[0])

    return None


def get_stack_ranked_config_ordering(
    generated_message_type: str,
    archetype_id: Optional[int] = -1,
    client_id: Optional[int] = -1,
    prospect_id: Optional[int] = -1,
    only_active_configs: bool = False,
    discluded_config_ids: Optional[list[int]] = [],
):
    """Get the stack ranked message generation configuration ordering for a client archetype"""
    ordered_srmgcs = (
        StackRankedMessageGenerationConfiguration.query.filter(
            or_(
                and_(  # default configurations
                    StackRankedMessageGenerationConfiguration.archetype_id == None,
                    StackRankedMessageGenerationConfiguration.client_id == None,
                ),
                and_(  # archetype specific configurations
                    StackRankedMessageGenerationConfiguration.archetype_id
                    == archetype_id,
                    StackRankedMessageGenerationConfiguration.client_id == client_id,
                ),
                and_(  # client specific configurations
                    StackRankedMessageGenerationConfiguration.archetype_id == None,
                    StackRankedMessageGenerationConfiguration.client_id == client_id,
                ),
            ),
        )
        .filter(
            StackRankedMessageGenerationConfiguration.generated_message_type
            == generated_message_type,
            StackRankedMessageGenerationConfiguration.id.notin_(discluded_config_ids),
        )
        .order_by(
            StackRankedMessageGenerationConfiguration.priority.desc(),
            text("archetype_id IS NULL"),
            text("client_id IS NULL"),
        )
        .all()
    )

    if prospect_id and prospect_id != -1:
        research_points = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
        research_point_types = [
            research_point.research_point_type.value
            for research_point in research_points
        ]

        filtered_ordered_srmgcs = []
        for srmgc in ordered_srmgcs:
            if only_active_configs and not srmgc.active:
                continue
            if srmgc.configuration_type == ConfigurationType.DEFAULT:
                if any(
                    [rpt in research_point_types for rpt in srmgc.research_point_types]
                ):
                    filtered_ordered_srmgcs.append(srmgc)
            elif srmgc.configuration_type == ConfigurationType.STRICT:
                if all(
                    [rpt in research_point_types for rpt in srmgc.research_point_types]
                ):
                    filtered_ordered_srmgcs.append(srmgc)
        ordered_srmgcs = filtered_ordered_srmgcs

    priority_groups = {}
    for srgmc in ordered_srmgcs:
        srgmc: StackRankedMessageGenerationConfiguration = srgmc
        if not priority_groups.get(srgmc.priority):
            priority_groups[srgmc.priority] = []
        priority_groups[srgmc.priority].append(srgmc)

    priority_group_list = [
        priority_groups[k] for k in sorted(priority_groups, reverse=True)
    ]

    return priority_group_list


def toggle_stack_ranked_message_configuration_active(
    stack_ranked_configuration_id: int,
) -> tuple[bool, str]:
    """Toggle the active status of a stack ranked message generation configuration"""
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=stack_ranked_configuration_id
        ).first()
    )
    if not srmgc:
        return False, "Stack ranked message generation configuration does not exist"
    if srmgc.always_enable and srmgc.active:
        return False, "This message configuration is meant to always be on."
    srmgc.active = not srmgc.active
    db.session.add(srmgc)
    db.session.commit()
    return True, "OK"


def get_prompts_from_stack_ranked_config(
    configuration_id: int, prospect_id: int, list_of_research_points: list
):
    from src.message_generation.services import generate_prompt

    prospect_prompt, _ = generate_prompt(
        prospect_id,
        "\n-".join(list_of_research_points),
    )

    config = StackRankedMessageGenerationConfiguration.query.filter_by(
        id=configuration_id
    ).first()
    full_prompt = config.computed_prompt.format(prompt=prospect_prompt)

    return {
        "prospect_prompt": prospect_prompt,
        "full_prompt": full_prompt,
    }


def get_stack_ranked_configurations(client_sdr_id: int, archetype_id: Optional[int]):

    from model_import import StackRankedMessageGenerationConfiguration, ClientSDR

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    archetypes: list[ClientArchetype] = ClientArchetype.query.filter_by(
        client_sdr_id=sdr.id
    ).all()

    if archetype_id:
        archetypes = [ClientArchetype.query.get(archetype_id)]

    archetype_ids = [archetype.id for archetype in archetypes]
    configs: list[StackRankedMessageGenerationConfiguration] = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            client_id=sdr.client_id, generated_message_type="LINKEDIN"
        )
        .filter(
            or_(
                StackRankedMessageGenerationConfiguration.archetype_id.in_(
                    archetype_ids
                ),
                StackRankedMessageGenerationConfiguration.archetype_id == None,
            )
        )
        .all()
    )

    return configs


def get_stack_ranked_configuration_details(client_sdr_id: int, config_id: int):
    config: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=config_id,
        ).first()
    )
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if config.client_id != client_sdr.client_id:
        return None, "Configuration does not belong to this client"

    return config.to_dict(), "OK"


def get_random_prospect(
    client_id: int,
    overall_status: ProspectOverallStatus,
    archetype_id: Optional[int] = None,
):
    from model_import import Prospect

    if archetype_id:
        prospects = (
            Prospect.query.filter_by(
                client_id=client_id,
                archetype_id=archetype_id,
                overall_status=overall_status,
            )
            .order_by(Prospect.icp_fit_score.desc())
            .limit(50)
            .all()
        )
        if len(prospects) > 0:
            return random.choice(prospects)

    return (
        Prospect.query.filter_by(client_id=client_id, overall_status=overall_status)
        .order_by(func.random())
        .first()
    )


def get_random_research_point(
    client_id: int,
    research_point_type: str,
    archetype_id: Optional[int] = None,
    prospect_id: Optional[int] = None,
):
    query = """
    select value, research_point.research_point_type, research_point.id
    from research_point
        join research_payload on research_payload.id = research_point.research_payload_id
        join prospect on prospect.id = research_payload.prospect_id
    where 
        prospect.client_id = {client_id} 
        and research_point_type = '{research_point_type}'
        and (
            {archetype_id_not_present} or prospect.archetype_id = {archetype_id}
        ) and (
            {prospect_id_not_present} or prospect.id = {prospect_id}
        )
    order by random()
    limit 1;""".format(
        client_id=str(client_id),
        research_point_type=research_point_type,
        archetype_id_not_present=not archetype_id,
        archetype_id=str(archetype_id or -1),
        prospect_id_not_present=not prospect_id,
        prospect_id=str(prospect_id or -1),
    )
    result = db.engine.execute(query)
    data = result.first()
    if data:
        return data[0], data[1], data[2]
    return None, None, None


def random_cta_for_prospect(prospect_id: int):
    from model_import import GeneratedMessageCTA, Prospect

    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    archetype_id = prospect.archetype_id
    ctas = (
        GeneratedMessageCTA.query.filter_by(archetype_id=archetype_id)
        .filter_by(active=True)
        .order_by(func.random())
        .first()
    )
    if not ctas:
        return "", -1
    return ctas.text_value, ctas.id


def get_sample_prompt_from_config_details(
    generated_message_type: str,
    research_point_types: list[str],
    configuration_type: str,
    client_id: int,
    archetype_id: Optional[int] = None,
    override_prospect_id: Optional[int] = None,
):
    from model_import import Prospect, ResearchPayload, ResearchPoints, ResearchType
    from src.message_generation.services import generate_prompt

    if not override_prospect_id:
        random_prospect = get_random_prospect(
            client_id=client_id,
            archetype_id=archetype_id,
            overall_status=ProspectOverallStatus.PROSPECTED,
        )
        if not random_prospect:
            return "", None, [], None, {}, None
        prospect_id = random_prospect.id
    else:
        prospect_id = override_prospect_id

    get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

    research_points = []
    research_point_ids = []
    selected_research_point_types = []

    has_custom = False
    if "CUSTOM" in research_point_types:
        has_custom = True

    prospect_research_point_types = [
        x.research_point_type.value
        for x in ResearchPoints.get_research_points_by_prospect_id(prospect_id)
    ]
    research_point_types = [
        research_point_type
        for research_point_type in research_point_types
        if research_point_type in prospect_research_point_types
    ]

    if configuration_type == "DEFAULT":
        research_point_types = random.sample(research_point_types, 2)
        if has_custom:
            research_point_types.append("CUSTOM")

    for rpt in research_point_types:
        rp, rp_type, id = get_random_research_point(
            client_id=client_id,
            research_point_type=rpt,
            archetype_id=archetype_id,
            prospect_id=prospect_id,
        )
        if not rp:
            continue
        research_points.append(rp)
        research_point_ids.append(id)

        selected_research_point_types.append(rp_type)

    cta_id = None
    if generated_message_type == "LINKEDIN":
        cta, cta_id = random_cta_for_prospect(prospect_id=prospect_id)
        research_points.append(cta)
        cta_id = cta_id

    notes = "\n-".join(research_points)
    prompt, bio_data = generate_prompt(prospect_id=prospect_id, notes=notes)

    return (
        prompt,
        selected_research_point_types,
        research_point_ids,
        cta_id,
        bio_data,
        prospect_id,
    )


def generate_completion_for_prospect(
    client_sdr_id: int, prospect_id: int, computed_prompt: str
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    prospect: Prospect = Prospect.query.get(prospect_id)
    if not prospect or prospect.client_id != client_sdr.client_id:
        return None, "Prospect does not exist or does not belong to this client"

    prompt, _, _, _, _, _ = get_sample_prompt_from_config_details(
        generated_message_type="LINKEDIN",
        research_point_types=[x.value for x in ResearchPointType],
        configuration_type="DEFAULT",
        client_id=client_sdr.client_id,
        archetype_id=prospect.archetype_id,
        override_prospect_id=prospect_id,
    )
    if not prompt:
        return None, "Could not generate prompt"

    completion, _ = get_computed_prompt_completion(
        computed_prompt=computed_prompt,
        prompt=prompt,
    )

    return completion, "OK"


def update_stack_ranked_configuration_prompt_and_instruction(
    configuration_id: int, new_prompt: str, client_sdr_id: Optional[int] = None
):
    """Update the prompt and instruction of a stack ranked message generation configuration"""

    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=configuration_id
        ).first()
    )
    if not srmgc:
        return False, "Stack ranked message generation configuration does not exist"

    if client_sdr_id:
        client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        if client_sdr.client_id != srmgc.client_id:
            return (
                False,
                "Stack ranked message generation configuration does not belong to this client",
            )

    srmgc.computed_prompt = new_prompt
    db.session.add(srmgc)
    db.session.commit()
    return True, "OK"


def set_active_stack_ranked_configuration_tool(configuration_id: int, set_active: bool):
    """Set the active stack ranked configuration tool"""

    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=configuration_id
        ).first()
    )
    if not srmgc:
        return False, "Stack ranked message generation configuration does not exist"
    srmgc.active = set_active
    db.session.add(srmgc)
    db.session.commit()
    return True, "OK"
