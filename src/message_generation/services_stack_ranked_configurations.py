from model_import import StackRankedMessageGenerationConfiguration, ResearchPointType


def create_stack_ranked_configuration(
    research_point_types: list[ResearchPointType],
):
    """Create a new stack ranked message generation configuration"""
    pass


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
