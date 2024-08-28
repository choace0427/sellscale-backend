from typing import Optional
from model_import import Strategies, StrategyClientArchetypeMapping, ClientSDR
from app import db
from src.client.models import ClientArchetype
from src.ml.models import LLM
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.strategies.models import StrategyStatuses

def create_strategy(
    client_sdr_id: int,
    name: str,
    description: str,
    client_archetype_ids: list[int],
    start_date: str,
    end_date: str,
):
    """
    Create a strategy.
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    strategy = Strategies(
        title=name,
        description=description,
        status=StrategyStatuses.NOT_STARTED,
        created_by=client_sdr_id,
        client_id=client_sdr.client_id,
        start_date=start_date,
        end_date=end_date,
    )

    db.session.add(strategy)
    db.session.commit()

    for client_archetype_id in client_archetype_ids:
        create_strategy_client_archetype_mapping(
            client_sdr_id=client_sdr_id,
            strategy_id=strategy.id,
            client_archetype_id=client_archetype_id,
        )

    return strategy.to_dict()

def create_strategy_client_archetype_mapping(
    client_sdr_id: int,
    strategy_id: int,
    client_archetype_id: int,
):
    """
    Create a mapping between a strategy and a client archetype.
    """
    existing_mapping = StrategyClientArchetypeMapping.query.filter_by(
        strategy_id=strategy_id,
        client_archetype_id=client_archetype_id,
    ).first()
    if existing_mapping:
        return existing_mapping.to_dict()
    
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if client_archetype.client_id != client_sdr.client_id:
        return None

    strategy_client_archetype_mapping = StrategyClientArchetypeMapping(
        strategy_id=strategy_id,
        client_archetype_id=client_archetype_id,
    )

    db.session.add(strategy_client_archetype_mapping)
    db.session.commit()

    return strategy_client_archetype_mapping.to_dict()

def delete_strategy_archetype_mapping(
    client_sdr_id: int,
    strategy_id: int,
    client_archetype_id: int,
):
    """
    Delete a mapping between a strategy and a client archetype.
    """
    strategy: Strategies = Strategies.query.get(strategy_id)
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if strategy.client_id != client_sdr.client_id:
        raise ValueError("Strategy does not belong to the same client as the SDR")

    mapping = StrategyClientArchetypeMapping.query.filter_by(
        strategy_id=strategy_id,
        client_archetype_id=client_archetype_id,
    ).first()
    if not mapping:
        return False
    
    db.session.delete(mapping)
    db.session.commit()

    return True

def get_strategy_dict(strategy_id: int):
    """
    Get a strategy by its ID.
    """
    strategy: Strategies = Strategies.query.get(strategy_id)
    return strategy.to_dict(deep_get=True)

def edit_strategy(
    client_sdr_id: int,
    strategy_id: int,
    new_title: Optional[str] = None,
    new_description: Optional[str] = None,
    new_status: Optional[StrategyStatuses] = None,
    new_archetypes: Optional[list[int]] = None,
    new_start_date: Optional[str] = None,
    new_end_date: Optional[str] = None,
):
    """
    Edit a strategy.
    """
    strategy: Strategies = Strategies.query.get(strategy_id)

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if strategy.client_id != client_sdr.client_id:
        raise ValueError("Strategy does not belong to the same client as the SDR")

    if new_title:
        strategy.title = new_title
    if new_description:
        strategy.description = new_description
    if new_status:
        strategy.status = new_status
    if new_start_date:
        strategy.start_date = new_start_date
    if new_end_date:
        strategy.end_date = new_end_date

    db.session.add(strategy)
    db.session.commit()

    if new_archetypes:
        # get all archetypes and delete all mappings
        existing_mappings = StrategyClientArchetypeMapping.query.filter_by(strategy_id=strategy_id).all()
        for mapping in existing_mappings:
            db.session.delete(mapping)
        db.session.commit()

        for client_archetype_id in new_archetypes:
            create_strategy_client_archetype_mapping(
                client_sdr_id=client_sdr_id,
                strategy_id=strategy_id,
                client_archetype_id=client_archetype_id,
            )

    return strategy.to_dict()

def toggle_strategy_client_archetype_mapping(
    client_sdr_id: int,
    strategy_id: int,
    client_archetype_id: int,
):
    """
    Toggle a mapping between a strategy and a client archetype.
    """
    existing_mapping = StrategyClientArchetypeMapping.query.filter_by(
        strategy_id=strategy_id,
        client_archetype_id=client_archetype_id,
    ).first()
    if existing_mapping:
        return delete_strategy_archetype_mapping(
            client_sdr_id=client_sdr_id,
            strategy_id=strategy_id,
            client_archetype_id=client_archetype_id,
        )
    else:
        return create_strategy_client_archetype_mapping(
            client_sdr_id=client_sdr_id,
            strategy_id=strategy_id,
            client_archetype_id=client_archetype_id,
        )

def get_all_strategies(client_sdr_id: int):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id
    
    query = """
    select 
        stragegies.id,
        stragegies.client_id,
        client_sdr.name,
        client_sdr.img_url,
        stragegies.title,
        stragegies.description,
        stragegies.created_at,
        stragegies.status,
        stragegies.start_date,
        stragegies.end_date,
        array_agg(distinct 
            concat(client_archetype.id, '#-#-#', client_archetype.emoji, ' ', client_archetype.archetype)
        ) archetypes,
        count(distinct prospect.id) filter (where
            prospect_status_records.to_status in ('SENT_OUTREACH') or
            prospect_email_status_records.to_status = 'SENT_OUTREACH'
        ) num_sent,
        count(distinct prospect.id) filter (where
            prospect_status_records.to_status in ('SENT_OUTREACH') or 
            prospect_email_status_records.to_status = 'SENT_OUTREACH'
        ) num_sent,
        count(distinct prospect.id) filter (where
            prospect_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION') or
            prospect_email_status_records.to_status in ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION')
        ) num_pos_response,
        count(distinct prospect.id) filter (where
            prospect_status_records.to_status in ('DEMO_SET') or
            prospect_email_status_records.to_status = 'DEMO_SET'
        ) num_demo
    from stragegies
        join client_sdr on client_sdr.id = stragegies.created_by
        left join strategy_client_archetype_mapping on strategy_client_archetype_mapping.strategy_id = stragegies.id
        left join client_archetype on client_archetype.id = strategy_client_archetype_mapping.client_archetype_id
        left join prospect on prospect.archetype_id = client_archetype.id
        left join prospect_status_records on prospect_status_records.prospect_id = prospect.id
        left join prospect_email on prospect_email.prospect_id = prospect.id 
        left join prospect_email_status_records on prospect_email_status_records.prospect_email_id = prospect_email.id
    where
        stragegies.client_id = {client_id}
    group by 
        1,2,3,4,5,6,7,8, 9, 10
    order by stragegies.start_date
    """.format(client_id=client_id)

    strategies = db.engine.execute(query)

    return [
        {
            "id": strategy.id,
            "client_id": strategy.client_id,
            "sdr_name": strategy.name,
            "sdr_img_url": strategy.img_url,
            "title": strategy.title,
            "description": strategy.description,
            "start_date": strategy.start_date,
            "end_date": strategy.end_date,
            "created_at": strategy.created_at,
            "status": strategy.status,
            "archetypes": [
                {
                    "id": int(archetype.split('#-#-#')[0]),
                    "emoji": archetype.split('#-#-#')[1].split(' ')[0],
                    "archetype": ' '.join(archetype.split('#-#-#')[1].split(' ')[1:])
                }
                for archetype in strategy.archetypes if "#-#-#" in archetype and archetype != "#-#-# "
            ],
            "num_sent": strategy.num_sent,
            "num_pos_response": strategy.num_pos_response,
            "num_demo": strategy.num_demo,
            "num_sent": strategy.num_sent,
        }
        for strategy in strategies
    ]




def create_task_list_from_strategy(selix_session_id: int) -> list[dict[str, str]]:
    """
    Creates an executable task list from a strategy.

    task_list: [
        {
            'title': 'Send out first email',
            'description': 'Send out the first email to the prospects',
        },
        ...
    ]
    """
    from src.chatbot.campaign_builder_assistant import get_action_calls
    from src.chatbot.models import SelixSession

    selix_session: SelixSession = SelixSession.query.get(selix_session_id)

    strategy_id = selix_session.memory.get("strategy_id", None)
    if not strategy_id:
        return []
    
    strategy: Strategies = Strategies.query.get(strategy_id)
    if not strategy:
        return []
    
    client_sdr: ClientSDR = ClientSDR.query.get(selix_session.client_sdr_id)
    action_calls: list[dict] = get_action_calls(selix_session_id)
    files = ""
    for action_call in action_calls:
        if action_call.get("action_function") == "analyze_file":
            files += '`{}` - {}'.format(action_call.get("action_params", {}).get("file_name", ""), action_call.get("action_params", {}).get("description", "")) + '\n'

    username = client_sdr.name
    strategy_name = strategy.title
    strategy_description = strategy.description
    
    llm: LLM = LLM.query.filter(
        LLM.name == 'generate_task_list_from_strategy'
    ).first()
    if not llm:
        raise ValueError("LLM not found")
    
    prompt = llm.user
    if not prompt:
        raise ValueError("LLM user prompt not found")
    
    prompt = prompt.format(
        files=files,
        username=username,
        strategy_name=strategy_name,
        strategy_description=strategy_description,
    )

    try:
        response = wrapped_chat_gpt_completion(
            messages=[
                {
                    'role': 'user',
                    'content': prompt,
                }
            ],
            model='gpt-4o',
            max_tokens=llm.max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "task_list_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": { "type": "string" },
                                        "description": { "type": "string" },
                                    },
                                    "required": ["title", "description"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["tasks"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            }
        )
    except Exception as e:
        print(e)
        response = {"error": "Error in generating task list."}
        print(response)

    import json
    response = json.loads(response)
    retval = response["tasks"]

    return retval

def generate_campaign_from_strategy(strategy_id: int) -> dict:
    """
    Generate a campaign from a strategy.
    """
    # get strategy
    strategy: Strategies = Strategies.query.get(strategy_id)

    # grab the strategy description
    strategy_description = strategy.description

    # grab the title
    strategy_title = strategy.title
    
    # Prepare the system message for the wrapped_chat_gpt_completion
    system_message = {
        "role": "system",
        "content": """
        You are a Selix AI assistant. Your task is to generate a campaign from a given strategy. 
        The frontend expects the data in the following format:

        type StrategyResponseData = {
          createdPersona: string; <-- The persona created for the campaign, campaign name.
          fitReason: string; <-- The reason why the campaign fits the target audience
          icpMatchingPrompt: string; <-- The description of the ICP for the campaign 
          emailSequenceKeywords: string[]; <-- Keywords that MUST be in the email sequence (max 3) do not make these conflicting with eachother.
          liSequenceKeywords: string[]; <-- Keywords that MUST be in the LinkedIn sequence (max 3). do not make these conflicting with eachother. 
          liGeneralAngle: string; <-- General angle for the LinkedIn sequence
          emailGeneralAngle: string; <-- General angle for the email sequence
          purpose: string; <-- Description of the Ideal Customer Profile. This should be a very detailed description of the ICP and written in the third person.
          liPainPoint: string; <-- Pain point for the LinkedIn sequence (optional, can be empty)
          withData: string; <-- Description of the data used for the campaign
          liAssetIngestor: string; <-- Any other information for the campaign
          emailAssetIngestor: string; <-- Any other information for the campaign from the strategy.
        };

        Please provide the data in the above format with appropriate descriptions for each field.
        """
    }

    # Prepare the user message with the strategy details
    user_message = {
        "role": "user",
        "content": f"""
        Strategy Title: {strategy_title}
        Strategy Description: {strategy_description}
        """
    }

    # Get the response from the wrapped_chat_gpt_completion
    response = wrapped_chat_gpt_completion(
        messages=[system_message, user_message],
        model="gpt-4o-2024-08-06",
        max_tokens=700,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "strategy_response_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "createdPersona": { "type": "string" },
                        "fitReason": { "type": "string" },
                        "icpMatchingPrompt": { "type": "string" },
                        "emailSequenceKeywords": { "type": "array", "items": { "type": "string" } },
                        "liSequenceKeywords": { "type": "array", "items": { "type": "string" } },
                        "liGeneralAngle": { "type": "string" },
                        "emailGeneralAngle": { "type": "string" },
                        "purpose": { "type": "string" },
                        "liPainPoint": { "type": "string" },
                        "ctaTarget": { "type": "string" },
                        "withData": { "type": "string" },
                        "liAssetIngestor": { "type": "string" },
                        "emailAssetIngestor": { "type": "string" }
                    },
                    "required": ["createdPersona", "fitReason", "icpMatchingPrompt", "emailSequenceKeywords", "liSequenceKeywords", "liGeneralAngle", "emailGeneralAngle", "purpose", "liPainPoint", "ctaTarget", "withData", "liAssetIngestor", "emailAssetIngestor"],
                    "additionalProperties": False
                },
            }
        }
    )

    import json

    # Parse the response
    response_data = json.loads(response)

    # Ensure the response data matches the expected format
    strategy_response_data = {
        "createdPersona": response_data.get("createdPersona", ""),
        "fitReason": response_data.get("fitReason", ""),
        "icpMatchingPrompt": response_data.get("icpMatchingPrompt", ""),
        "emailSequenceKeywords": response_data.get("emailSequenceKeywords", []),
        "liSequenceKeywords": response_data.get("liSequenceKeywords", []),
        "liGeneralAngle": response_data.get("liGeneralAngle", ""),
        "emailGeneralAngle": response_data.get("emailGeneralAngle", ""),
        "purpose": response_data.get("purpose", ""),
        "liPainPoint": response_data.get("liPainPoint", ""),
        "ctaTarget": response_data.get("ctaTarget", ""),
        "withData": response_data.get("withData", ""),
        "liAssetIngestor": response_data.get("liAssetIngestor", ""),
        "emailAssetIngestor": response_data.get("emailAssetIngestor", "")
    }

    return strategy_response_data