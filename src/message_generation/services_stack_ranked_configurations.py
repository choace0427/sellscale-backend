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
from typing import Optional
from app import db


def compute_prompt(stack_ranked_configuration_id: int):
    """Compute the prompt for a stack ranked message generation configuration"""
    pass


def create_stack_ranked_configuration(
    configuration_type: str,
    research_point_types: list[ResearchPointType],
    generated_message_ids: list[int],
    instruction: str,
    generated_message_type: str,
    name: Optional[str] = None,
    client_id: Optional[int] = None,
    archetype_id: Optional[int] = None,
) -> tuple[bool, str]:
    """Create a new stack ranked message generation configuration"""
    for generated_message_id in generated_message_ids:
        generated_message: GeneratedMessage = GeneratedMessage.query.filter_by(
            id=generated_message_id
        ).first()
        if not generated_message:
            return False, "Generated message does not exist"
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
            generated_message_ids=generated_message_ids,
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


def edit_stack_ranked_configuration_generated_message_ids(
    stack_ranked_configuration_id: int,
    generated_message_ids: list[int],
):
    """Edit the generated message ids of a stack ranked message generation configuration"""
    srmgc: StackRankedMessageGenerationConfiguration = (
        StackRankedMessageGenerationConfiguration.query.filter_by(
            id=stack_ranked_configuration_id
        ).first()
    )
    if not srmgc:
        return False, "Stack ranked message generation configuration does not exist"
    srmgc.generated_message_ids = generated_message_ids
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


def get_top_stack_ranked_config_ordering(generated_message_type: str, prospect_id: int):
    """Get the top stack ranked message generation configuration ordering for a client archetype"""
    from model_import import Prospect

    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    client_id = prospect.client_id
    archetype_id = prospect.archetype_id
    stack_ranked_config_ordering: list = get_stack_ranked_config_ordering(
        generated_message_type, archetype_id, client_id, prospect_id
    )
    if len(stack_ranked_config_ordering) > 0:
        return stack_ranked_config_ordering[0]
    return None


def get_stack_ranked_config_ordering(
    generated_message_type: str,
    archetype_id: Optional[int] = -1,
    client_id: Optional[int] = -1,
    prospect_id: Optional[int] = -1,
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
        )
        .order_by(
            StackRankedMessageGenerationConfiguration.priority.desc(),
        )
        .all()
    )

    if prospect_id:
        research_points = ResearchPoints.get_research_points_by_prospect_id(prospect_id)
        research_point_types = [
            research_point.research_point_type.value
            for research_point in research_points
        ]

        filtered_ordered_srmgcs = []
        for srmgc in ordered_srmgcs:
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

    return [srmgc.to_dict() for srmgc in ordered_srmgcs]
