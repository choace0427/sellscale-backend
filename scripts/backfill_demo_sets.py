from app import db


def get_prospects_where_conversation_is_scheduling():
    query = '''
    SELECT prospect.client_id, client.company, prospect.id, prospect.li_conversation_urn_id
    FROM prospect
    LEFT JOIN client
    ON client.id = prospect.client_id
    WHERE (prospect.overall_status = 'ACTIVE_CONVO' OR prospect.status = 'ACTIVE_CONVO_SCHEDULING' 
    OR prospect.status = 'SCHEDULING') AND prospect.client_id IN (89,88,87,80,75,47,1) 
    AND prospect.li_conversation_urn_id IS NOT NULL;
    '''

    response = db.session.execute(query).fetchall()

    company_prospect_map = {}

    for row in response:
        if row[0] not in company_prospect_map:
            company_prospect_map[row[0]] = {
                "company": row[1],
                "prospects": [
                    {"prospect_id": row[2], "li_conversation_urn_id": row[3]}
                ]
            }
        else:
            company_prospect_map[row[0]]["prospects"].append(
                {"prospect_id": row[2], "li_conversation_urn_id": row[3]}
            )

    print(company_prospect_map)
    #
    for client_id, data in company_prospect_map.items():
        for prospect in data["prospects"]:
            prospect_id = prospect["prospect_id"]
            thread_urn_id = prospect["li_conversation_urn_id"]
            detect_demo_set(thread_urn_id, prospect_id, company_prospect_map, client_id)

    return company_prospect_map


def detect_demo_set(thread_urn_id: str, prospect_id: int, company_prospect_map, client_id):
    print("Detecting for prospect_id", prospect_id)
    from src.prospecting.models import Prospect
    prospect: Prospect = Prospect.query.get(prospect_id)
    from src.client.models import ClientSDR
    clientSDR: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    from src.prospecting.models import ProspectOverallStatus
    if prospect.overall_status not in [ProspectOverallStatus.ACTIVE_CONVO]:
        return

    # Get the conversation entries for the thread
    from src.li_conversation.models import LinkedinConversationEntry
    conversation_entries = (
        LinkedinConversationEntry.query.filter(
            LinkedinConversationEntry.thread_urn_id == thread_urn_id,
            )
        .order_by(LinkedinConversationEntry.created_at.asc())
        .all()
    )

    latest_message = conversation_entries[-1]

    # Run the demo set ruleset
    if latest_message:
        message_lowered = latest_message.message.lower()
        from src.heuristic_keywords.heuristics import demo_key_words
        for key_word in demo_key_words:
            # if key_word in message_lowered:
            if True:
                messages = [x.message for x in conversation_entries]
                from src.ml.services import chat_ai_verify_demo_set
                is_demo_set = chat_ai_verify_demo_set(messages, prospect.full_name)
                if is_demo_set:
                    print("Got a demo set")
                    messages = messages[-5:] if len(messages) >= 5 else messages
                    messages_joined = '\n'.join(messages)
                    from src.utils.slack import send_slack_message
                    from src.utils.slack import URL_MAP
                    send_slack_message(
                        message="Demo set detected 🎉",
                        webhook_urls=[URL_MAP["ops-demo-set-detection"]],
                        blocks=[
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Demo set detected 🎉",
                                    "emoji": True,
                                },
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "```{messages_joined}```\nThese are the last few messages.\n⏰ Recommended Status: *\"DEMO_SET\"*".format(
                                        messages_joined=messages_joined
                                    ),
                                },
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"> 🤖 *Rep*: {clientSDR.name}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"> 👥 *Prospect*: {prospect.full_name}",
                                    },
                                ],
                            },
                            {"type": "divider"},
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "🎊🎈 Take action and mark as ✅ (if wrong, inform an engineer)",
                                },
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Direct Link ➡️",
                                },
                                "accessory": {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "Link", "emoji": True},
                                    "url": f"https://app.sellscale.com/authenticate?stytch_token_type=direct&token={clientSDR.auth_token}&redirect=prospects/{prospect.id}",
                                    "action_id": "button-action",
                                },
                            },
                            {"type": "divider"},
                        ],
                    )

                    # Perform the demo set action
                    # Setting the demoset meta data
                    from src.prospecting.services import patch_prospect
                    success = patch_prospect(
                        prospect_id=prospect_id,
                        meta_data=(
                            {
                                **prospect.meta_data,
                                "demo_set": {"type": "DIRECT", "description": "Demo set detected by OpenAI"},
                            }
                            if prospect.meta_data
                            else {"demo_set": {"type": "DIRECT", "description": "Demo set detected by OpenAI"}}
                        )
                    )

                    # Set the actual status
                    # Linkedin only
                    from src.prospecting.models import ProspectStatus
                    from src.prospecting.services import update_prospect_status_linkedin
                    update_status = update_prospect_status_linkedin(
                        prospect_id=prospect_id,
                        new_status=ProspectStatus.DEMO_SET,
                    )

                    prospect.status = ProspectStatus.DEMO_SET
                    db.session.add(prospect)
                    db.session.commit()

                    if success and update_status:
                        send_slack_message(
                            message="Set Status To Demo Set 🎉",
                            webhook_urls=[URL_MAP["ops-demo-set-detection"]],
                            blocks=[
                                {
                                    "type": "header",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Status Changed to `DEMO_SET` 🎉",
                                        "emoji": True,
                                    },
                                },
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": "*Status Change*: Old `ACTIVE_CONVO` -> New `DEMO_SET`",
                                    },
                                },
                                {
                                    "type": "section",
                                    "fields": [
                                        {
                                            "type": "mrkdwn",
                                            "text": f"> 🤖 *Rep*: {clientSDR.name}",
                                        },
                                        {
                                            "type": "mrkdwn",
                                            "text": f"> 👥 *Prospect*: {prospect.full_name}",
                                        },
                                    ],
                                },
                            ]
                        )

                        company_prospect_map[client_id] = {
                            "company": company_prospect_map[client_id]["company"],
                            "prospect_id": prospect_id,
                            "li_conversation_urn_id": thread_urn_id,
                            "status": "DEMO_SET",
                            "message": "Demo set detected by OpenAI",
                        }

                else:
                    pass
                    # send_slack_message(
                    #     message=f"""
                    #     !!!!!❌ DEMO SET, Open AI said not a demo though. ❌!!!!!!
                    #     ```
                    #     {messages[-5:] if len(messages) >= 5 else messages}
                    #     ```
                    #     These are the last 5 messages.
                    #     ⏰ Current Status: "DEMO_SET"

                    #     > 🤖 Rep: {clientSDR.name} | 👥 Prospect: {prospect.full_name}

                    #     🎊🎈 Take action and mark as ✅ (if wrong, inform an engineer)
                    #     🔗 Direct Link: https://app.sellscale.com/authenticate?stytch_token_type=direct&token={clientSDR.auth_token}&redirect=prospects/{prospect.id}
                    #     """,
                    #     webhook_urls=[URL_MAP["ops-demo-set-detection"]],
                    # )
                break