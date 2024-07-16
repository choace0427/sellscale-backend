from typing import Optional
from model_import import Strategies, StrategyClientArchetypeMapping, ClientSDR
from app import db
from src.client.models import ClientArchetype
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
        status=StrategyStatuses.IN_PROGRESS,
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