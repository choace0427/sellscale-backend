from model_import import (
    StackRankedMessageGenerationConfiguration,
    ResearchPointType,
    ConfigurationType,
    GeneratedMessage,
    Client,
    ClientArchetype,
)
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
    name: Optional[str] = None,
    client_id: Optional[int] = None,
    archetype_id: Optional[int] = None,
) -> tuple[bool, Optional[str]]:
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
):
    """Edit the instruction of a stack ranked message generation configuration"""
    pass


def edit_stack_ranked_configuration_research_point_types(
    stack_ranked_configuration_id: int,
    research_point_types: list[ResearchPointType],
):
    """Edit the research point types of a stack ranked message generation configuration"""
    pass


def edit_stack_ranked_configuration_generated_message_ids(
    stack_ranked_configuration_id: int,
    generated_message_ids: list[int],
):
    """Edit the generated message ids of a stack ranked message generation configuration"""
    pass


def edit_stack_ranked_configuration_name(
    stack_ranked_configuration_id: int,
    name: str,
):
    """Edit the name of a stack ranked message generation configuration"""
    pass


def delete_stack_ranked_configuration(
    stack_ranked_configuration_id: int,
):
    """Delete a stack ranked message generation configuration"""
    pass
