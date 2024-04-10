from model_import import BumpFramework
from app import db
from src.bump_framework.models import BumpFrameworkToAssetMapping, BumpLength
from src.client.models import ClientArchetype, ClientAssets
from src.message_generation.services import clear_auto_generated_bumps
from src.prospecting.models import ProspectOverallStatus, ProspectStatus
from src.utils.slack import send_slack_message
from typing import Optional
from src.analytics.services import add_activity_log


def get_db_bump_messages(bump_id: int):
    """Get all bump messages"""
    messages = db.session.execute(
        f"""
            Select prospect.full_name, prospect.img_url, linkedin_conversation_entry.created_at, prospect.li_last_message_from_prospect message
            From linkedin_conversation_entry
	        Join prospect on prospect.li_conversation_urn_id = linkedin_conversation_entry.thread_urn_id
            Where linkedin_conversation_entry.bump_framework_id = {bump_id}
                and prospect.li_last_message_from_prospect is not null;
        """
    ).fetchall()

    messages = [dict(row) for row in messages]
    return {"data": messages, "message": "Success", "status_code": 200}


def send_new_framework_created_message(
    client_sdr_id: int,
    title: str,
    campaign_name: str,
    campaign_link: str,
    archetype_id: int,
):
    from model_import import ClientSDR, ClientArchetype

    ca: ClientArchetype = ClientArchetype.query.get(archetype_id)
    if not ca.active or not ca.linkedin_active:
        return

    webhook_url = ClientSDR.query.get(
        client_sdr_id
    ).client.pipeline_notifications_webhook_url
    message_sent = send_slack_message(
        message="",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⭐ New framework enabled: {title}".format(title=title),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Campaign:* `{campaign_name}`".format(
                        campaign_name=campaign_name
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Template:* {title}".format(title=title),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "View campaign sequence in Sight",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Campaign",
                        "emoji": True,
                    },
                    "value": campaign_link,
                    "url": campaign_link,
                    "action_id": "button-action",
                },
            },
        ],
        webhook_urls=[webhook_url],
    )
    if not message_sent:
        return False, "Failed to send update request."

    return True, "Success"


def get_bump_frameworks_for_sdr(
    client_sdr_id: int,
    overall_statuses: Optional[list[ProspectOverallStatus]] = [],
    substatuses: Optional[list[str]] = [],
    client_archetype_ids: Optional[list[int]] = [],
    exclude_client_archetype_ids: Optional[list[int]] = [],
    exclude_ss_default: Optional[bool] = False,
    unique_only: Optional[bool] = False,
    active_only: Optional[bool] = True,
    bumped_count: Optional[int] = None,
    default_only: Optional[bool] = False,
    include_archetype_sequence_id: Optional[int] = None,
    include_assets: Optional[bool] = False,
) -> list[dict]:
    """Get all bump frameworks for a given SDR and overall status

    Args:
        client_sdr_id (int): The id of the SDR
        overall_statuses (Optional[list[ProspectOverallStatus]], optional): The overall statuses of the bump frameworks. Defaults to [] which is ALL statuses.
        substatuses (Optional[list[str]], optional): The substatuses of the bump frameworks. Defaults to [] which is ALL substatuses.
        client_archetype_ids (Optional[list[int]], optional): The ids of the client archetypes. Defaults to [] which is ALL archetypes.
        exclude_client_archetype_ids (Optional[list[int]], optional): The ids of the client archetypes to exclude. Defaults to [] which is NO archetypes.
        excludeSSDefault (Optional[bool], optional): Whether to exclude bump frameworks with sellscale_default_generated. Defaults to False.
        activeOnly (Optional[bool], optional): Whether to only return active bump frameworks. Defaults to True.
        uniqueOnly (Optional[bool], optional): Whether to only return unique bump frameworks. Defaults to False.
        bumpedCount (Optional[int], optional): The number of times the bump framework has been bumped. Defaults to None.
        default_only (Optional[bool], optional): Whether to only return default bump frameworks. Defaults to False.

    Returns:
        list[dict]: A list of bump frameworks
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

    # TODO(Aakash) - this is the old way of doing it, we need to update this to the new way
    # bfs: list[BumpFramework] = BumpFramework.query.filter(
    #     BumpFramework.client_sdr_id == client_sdr_id,
    #     BumpFramework.client_archetype_id.in_(client_archetype_ids),
    #     BumpFramework.client_archetype_id.notin_(exclude_client_archetype_ids),
    #     BumpFramework.overall_status.in_(overall_statuses),
    # )

    # NEW
    bfs: list[BumpFramework] = BumpFramework.query.filter(
        db.or_(
            db.and_(
                BumpFramework.client_sdr_id == client_sdr_id,
                BumpFramework.client_archetype_id.in_(client_archetype_ids),
                BumpFramework.client_archetype_id.notin_(exclude_client_archetype_ids),
                BumpFramework.overall_status.in_(overall_statuses),
            ),
            db.and_(
                BumpFramework.client_sdr_id == None,
                BumpFramework.client_archetype_id == None,
                BumpFramework.overall_status.in_(overall_statuses),
                BumpFramework.default == True,
            ),
        )
    )

    # If substatuses is specified, filter by substatuses
    if len(substatuses) > 0:
        bfs = bfs.filter(BumpFramework.substatus.in_(substatuses))

    # If exclude_ss_default is specified, filter by sellscale_default_generated
    if exclude_ss_default:
        bfs = bfs.filter(BumpFramework.sellscale_default_generated == False)

    # If active_only is specified, filter by active
    if active_only:
        bfs = bfs.filter(BumpFramework.active == True)

    # If bumped_count is specified, filter by bumped_count
    if bumped_count is not None and ProspectOverallStatus.BUMPED in overall_statuses:
        bfs = bfs.filter(BumpFramework.bumped_count == bumped_count)

    if default_only:
        bfs = bfs.filter(BumpFramework.default == True)

    bfs: list[BumpFramework] = bfs.all()

    if include_archetype_sequence_id:
        ca: ClientArchetype = ClientArchetype.query.filter(
            ClientArchetype.id == include_archetype_sequence_id,
            ClientArchetype.client_sdr_id == client_sdr_id,
        ).first()
        if ca:
            additional_bfs: list[BumpFramework] = (
                BumpFramework.query.filter(
                    BumpFramework.client_archetype_id == include_archetype_sequence_id,
                    BumpFramework.overall_status.in_(
                        [
                            ProspectOverallStatus.ACCEPTED,
                            ProspectOverallStatus.BUMPED,
                        ]
                    ),
                    BumpFramework.active == True,
                    BumpFramework.default == True,
                    BumpFramework.bumped_count < ca.li_bump_amount,
                )
                .order_by(BumpFramework.bumped_count)
                .all()
            )

            for bf in additional_bfs:
                if bf.id not in [bf.id for bf in bfs]:
                    bfs.append(bf)

    # If unique_only is specified, filter by unique
    if unique_only:
        seen = set()
        bf_unique = []
        for bf in bfs:
            seen_tuple = (bf.title, bf.description)
            if seen_tuple in seen:
                continue
            bf_unique.append(bf)
            seen.add(seen_tuple)
        bfs = bf_unique

    bf_dicts = [bf.to_dict() for bf in bfs]

    if include_assets:
        # For each bf, get the assets and add them to the bf dict
        for bf in bf_dicts:
            bf["assets"] = get_all_bump_framework_assets(bf["id"])

    return bf_dicts


def get_bump_framework_count_for_sdr(
    client_sdr_id: int, client_archetype_ids: Optional[list[int]] = []
) -> dict:
    """Gets the counts for bump frameworks that belong to a Client SDR in a given archetype.

    Args:
        client_sdr_id (int): _description_
        client_archetype_ids (Optional[list[int]], optional): Which archetypes to retrieve the bump frameworks. Defaults to all archetypes.
    """
    bump_frameworks = get_bump_frameworks_for_sdr(
        client_sdr_id, client_archetype_ids=client_archetype_ids
    )

    counts = {
        "total": len(bump_frameworks),
        ProspectOverallStatus.ACCEPTED.value: 0,
        ProspectOverallStatus.BUMPED.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUESTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_QUAL_NEEDED.value: 0,
        ProspectStatus.ACTIVE_CONVO_OBJECTION.value: 0,
        ProspectStatus.ACTIVE_CONVO_NEXT_STEPS.value: 0,
        ProspectStatus.ACTIVE_CONVO_SCHEDULING.value: 0,
        ProspectStatus.ACTIVE_CONVO_REVIVAL.value: 0,
    }
    for bump_framework in bump_frameworks:
        if bump_framework.get("overall_status") in counts:
            counts[bump_framework.get("overall_status")] += 1
        if bump_framework.get("substatus") in counts:
            counts[bump_framework.get("substatus")] += 1

    return counts


def create_bump_framework(
    client_sdr_id: int,
    client_archetype_id: int,
    title: str,
    description: str,
    overall_status: ProspectOverallStatus,
    length: BumpLength,
    additional_instructions: Optional[str] = None,
    bumped_count: int = None,
    bump_delay_days: int = 2,
    active: bool = True,
    substatus: Optional[str] = None,
    default: Optional[bool] = False,
    sellscale_default_generated: Optional[bool] = False,
    use_account_research: Optional[bool] = True,
    bump_framework_template_name: Optional[str] = None,
    bump_framework_human_readable_prompt: Optional[str] = None,
    additional_context: Optional[str] = None,
    transformer_blocklist: Optional[list] = [],
    asset_ids: Optional[list[int]] = [],
) -> int:
    """Create a new bump framework, if default is True, set all other bump frameworks to False

    Args:
        client_sdr_id (int): The id of the SDR
        client_archetype_id (int): The id of the client archetype
        title (str): The title of the bump framework
        description (str): The description of the bump framework
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        length (BumpLength): The length of the bump framework
        additional_instructions (Optional[str], optional): The additional instructions of the bump framework. Defaults to None.
        bumped_count (int, optional): The number which corresponds to which bump in the sequence this BF appears. Defaults to None.
        bump_delay_days (int, optional): The number of days to wait before bumping. Defaults to 2.
        active (bool, optional): Whether the bump framework is active. Defaults to True.
        substatus (Optional[str], optional): The substatus of the bump framework. Defaults to None.
        default (Optional[bool], optional): Whether the bump framework is the default. Defaults to False.
        sellscale_default_generated (Optional[bool], optional): Whether the bump framework was generated by SellScale. Defaults to False.

    Returns:
        int: The id of the newly created bump framework
    """
    if default and client_archetype_id:
        all_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter_by(
            client_sdr_id=client_sdr_id,
            client_archetype_id=client_archetype_id,
            overall_status=overall_status,
        )
        if overall_status == ProspectOverallStatus.BUMPED and bumped_count is not None:
            all_bump_frameworks = all_bump_frameworks.filter_by(
                bumped_count=bumped_count
            )
        all_bump_frameworks = all_bump_frameworks.all()
        for bump_framework in all_bump_frameworks:
            bump_framework.default = False
            db.session.add(bump_framework)

    if length not in [BumpLength.LONG, BumpLength.SHORT, BumpLength.MEDIUM]:
        length = BumpLength.MEDIUM

    # Create the Bump Framework
    bump_framework = BumpFramework(
        client_sdr_id=client_sdr_id,
        client_archetype_id=client_archetype_id,
        description=description,
        additional_instructions=additional_instructions,
        title=title,
        overall_status=overall_status,
        substatus=substatus,
        bump_length=length,
        bumped_count=bumped_count,
        bump_delay_days=bump_delay_days,
        active=active,
        default=default,
        sellscale_default_generated=sellscale_default_generated,
        use_account_research=use_account_research,
        bump_framework_template_name=bump_framework_template_name,
        bump_framework_human_readable_prompt=bump_framework_human_readable_prompt,
        additional_context=additional_context,
        transformer_blocklist=transformer_blocklist,
    )
    db.session.add(bump_framework)
    db.session.commit()
    bump_framework_id = bump_framework.id

    # Create asset mappings
    for asset_id in asset_ids or []:
        mapping = BumpFrameworkToAssetMapping(
            bump_framework_id=bump_framework_id,
            client_assets_id=asset_id,
        )
        db.session.add(mapping)
    db.session.commit()

    # Add an activity log
    add_activity_log(
        client_sdr_id=client_sdr_id,
        type="BUMP-FRAMEWORK-CREATED",
        name="Bump Framework Created",
        description=f"Created a new bump framework: {title}",
    )

    return bump_framework_id


def modify_bump_framework(
    client_sdr_id: int,
    client_archetype_id: int,
    bump_framework_id: int,
    overall_status: ProspectOverallStatus,
    length: BumpLength,
    title: Optional[str],
    description: Optional[str],
    additional_instructions: Optional[str] = None,
    bumped_count: Optional[int] = None,
    bump_delay_days: Optional[int] = None,
    use_account_research: Optional[bool] = None,
    default: Optional[bool] = False,
    blocklist: Optional[list] = None,
    additional_context: Optional[str] = None,
    bump_framework_template_name: Optional[str] = None,
    bump_framework_human_readable_prompt: Optional[str] = None,
    human_feedback: Optional[str] = None,
    inject_calendar_times: Optional[bool] = False,
) -> bool:
    """Modify a bump framework

    Args:
        client_sdr_id (int): The id of the client SDR
        client_archetype_id(int): The id of the client Archetype
        bump_framework_id (int): The id of the bump framework
        overall_status (ProspectOverallStatus): The overall status of the bump framework
        length (BumpLength): The length of the bump framework
        title (Optional[str]): The title of the bump framework
        description (Optional[str]): The description of the bump framework
        additional_instructions (Optional[str], optional): The additional instructions of the bump framework. Defaults to None.
        bumped_count (Optional[int], optional): The number which corresponds to which bump in the sequence this BF appears. Defaults to None.
        bump_delay_days (Optional[int], optional): The number of days to wait before bumping. Defaults to 2.
        default (Optional[bool]): Whether the bump framework is the default
        use_account_research (Optional[bool]): Whether the bump framework uses account research
        blocklist (Optional[list]): The transformer blocklist for the bump framework
        inject_calendar_times (Optional[bool]): Whether to inject calendar times into the bump framework

    Returns:
        bool: Whether the bump framework was modified
    """
    bump_framework: BumpFramework = BumpFramework.query.filter(
        BumpFramework.client_sdr_id == client_sdr_id,
        BumpFramework.id == bump_framework_id,
    ).first()

    if title:
        bump_framework.title = title
    if description:
        bump_framework.description = description
    if additional_instructions:
        bump_framework.additional_instructions = additional_instructions

    if length not in [BumpLength.LONG, BumpLength.SHORT, BumpLength.MEDIUM]:
        bump_framework.bump_length = BumpLength.MEDIUM
    else:
        bump_framework.bump_length = length

    if bumped_count:
        bump_framework.bumped_count = bumped_count

    if bump_delay_days:
        bump_framework.bump_delay_days = bump_delay_days

    if use_account_research is not None:
        bump_framework.use_account_research = use_account_research

    if inject_calendar_times is not None:
        bump_framework.inject_calendar_times = inject_calendar_times

    if blocklist != None:
        bump_framework.transformer_blocklist = blocklist

    if additional_context != None:
        bump_framework.additional_context = additional_context

    if bump_framework_template_name != None:
        bump_framework.bump_framework_template_name = bump_framework_template_name

    if bump_framework_human_readable_prompt != None:
        bump_framework.bump_framework_human_readable_prompt = (
            bump_framework_human_readable_prompt
        )

    if human_feedback != None:
        bump_framework.human_feedback = human_feedback

    if default and client_archetype_id:
        default_bump_frameworks: list[BumpFramework] = BumpFramework.query.filter(
            BumpFramework.client_sdr_id == client_sdr_id,
            BumpFramework.client_archetype_id == client_archetype_id,
            BumpFramework.overall_status == overall_status,
            BumpFramework.default == True,
        )
        if overall_status == ProspectOverallStatus.BUMPED and bumped_count is not None:
            default_bump_frameworks = default_bump_frameworks.filter(
                BumpFramework.bumped_count == bumped_count
            )
        default_bump_frameworks = default_bump_frameworks.all()
        for default_bump_framework in default_bump_frameworks:
            default_bump_framework.default = False
            db.session.add(default_bump_framework)
    bump_framework.default = default

    bump_framework.sellscale_default_generated = False

    db.session.add(bump_framework)
    db.session.commit()

    # Delete auto_generated_messages using this bump_framework
    clear_auto_generated_bumps(bump_framework_id)

    return True


def deactivate_bump_framework(client_sdr_id: int, bump_framework_id: int) -> None:
    """Deletes a BumpFramework entry by marking it as inactive

    Args:
        bump_framework_id (int): The id of the BumpFramework to delete

    Returns:
        None
    """
    bump_framework: BumpFramework = BumpFramework.query.filter(
        BumpFramework.id == bump_framework_id,
        BumpFramework.client_sdr_id == client_sdr_id,
    ).first()

    bump_framework.active = False
    db.session.add(bump_framework)
    db.session.commit()

    return


def activate_bump_framework(client_sdr_id: int, bump_framework_id: int) -> None:
    """Activates a BumpFramework entry by marking it as active

    Args:
        bump_framework_id (int): The id of the BumpFramework to activate

    Returns:
        None
    """
    bump_framework: BumpFramework = BumpFramework.query.filter(
        BumpFramework.id == bump_framework_id,
        BumpFramework.client_sdr_id == client_sdr_id,
    ).first()
    bump_framework.active = True
    db.session.add(bump_framework)
    db.session.commit()

    return


def clone_bump_framework(
    client_sdr_id: int, bump_framework_id: int, target_archetype_id: int
) -> int:
    """Clones (imports) an existent bump framework's attributes into a new bump framework under the target archetype

    Args:
        client_sdr_id (int): ID of the client SDR
        bump_framework_id (int): ID of the bump framework to clone
        target_archetype_id (int): ID of the target archetype

    Returns:
        int: ID of the new bump framework
    """
    archetype: ClientArchetype = ClientArchetype.query.get(target_archetype_id)
    if not archetype:
        return -1
    elif archetype.client_sdr_id != client_sdr_id:
        return -1

    existing_bf: BumpFramework = BumpFramework.query.get(bump_framework_id)
    if not existing_bf:
        return -1
    elif existing_bf.client_sdr_id != client_sdr_id:
        return -1

    new_framework_id: int = create_bump_framework(
        client_sdr_id=client_sdr_id,
        client_archetype_id=target_archetype_id,
        overall_status=existing_bf.overall_status,
        substatus=existing_bf.substatus,
        length=existing_bf.bump_length,
        title=existing_bf.title,
        description=existing_bf.description,
        additional_instructions=existing_bf.additional_instructions,
        bumped_count=existing_bf.bumped_count,
        default=True,
        active=True,
        sellscale_default_generated=False,
    )

    return new_framework_id


def get_db_bump_sequence(archetype_id: int):
    """Get all bump sequence"""
    bump_frameworks = db.session.execute(
        f"""
            select
                concat('Follow Up #',
                bumped_count + 1, ': ',
                bump_framework.title) "Title",
                bump_framework.description "Description",
                client_archetype.id "project_id",
                bump_framework.id "bump_id"
            from bump_framework join client_archetype on client_archetype.id = bump_framework.client_archetype_id
            where bump_framework.client_archetype_id = {archetype_id}
            and bump_framework.overall_status in ('ACCEPTED', 'BUMPED')
            and bump_framework.active
            and bump_framework.default
            and bumped_count < client_archetype.li_bump_amount
            order by bumped_count;
        """
    ).fetchall()

    bump_frameworks = (
        BumpFramework.query.filter(
            BumpFramework.id.in_([bf["bump_id"] for bf in bump_frameworks]),
            BumpFramework.client_archetype_id == archetype_id,
            BumpFramework.active,
            BumpFramework.default,
            BumpFramework.overall_status.in_(
                [ProspectOverallStatus.ACCEPTED, ProspectOverallStatus.BUMPED]
            ),
        )
        .order_by(BumpFramework.bumped_count)
        .all()
    )

    bump_frameworks = [
        {
            "Title": f"Follow Up #{bf.bumped_count + 1}: {bf.title}",
            "Description": bf.description,
            "project_id": archetype_id,
            "bump_id": bf.id,
            **bf.to_dict(),
        }
        for bf in bump_frameworks
    ]

    return {"data": bump_frameworks, "message": "Success", "status_code": 200}


def create_bump_framework_asset_mapping(bump_framework_id: int, client_assets_id: int):
    mapping: BumpFrameworkToAssetMapping = BumpFrameworkToAssetMapping(
        bump_framework_id=bump_framework_id,
        client_assets_id=client_assets_id,
    )
    db.session.add(mapping)
    db.session.commit()
    return True


def delete_bump_framework_asset_mapping(
    bump_framework_to_asset_mapping_id: int,
):
    mapping: BumpFrameworkToAssetMapping = BumpFrameworkToAssetMapping.query.get(
        bump_framework_to_asset_mapping_id
    )
    if not mapping:
        return True

    db.session.delete(mapping)
    db.session.commit()
    return True


def get_all_bump_framework_assets(bump_framework_id: int):
    mappings: list[BumpFrameworkToAssetMapping] = (
        BumpFrameworkToAssetMapping.query.filter(
            BumpFrameworkToAssetMapping.bump_framework_id == bump_framework_id
        ).all()
    )
    asset_ids = [mapping.client_assets_id for mapping in mappings]
    assets: list[ClientAssets] = ClientAssets.query.filter(
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
