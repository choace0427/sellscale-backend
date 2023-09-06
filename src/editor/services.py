from app import db, celery
from model_import import Editor, EditorTypes
from src.utils.slack import *


def create_editor(
    name: str,
    email: str,
    editor_type: EditorTypes,
):
    editor = Editor(
        name=name,
        email=email,
        editor_type=editor_type,
    )
    db.session.add(editor)
    db.session.commit()
    return editor


def update_editor(
    name: str,
    email: str,
    editor_type: EditorTypes,
):
    editor = Editor.query.filter_by(email=email).first()
    if not editor:
        raise Exception(f"Editor not found for email {email}")
    editor.name = name
    editor.editor_type = editor_type
    db.session.commit()
    return editor


def toggle_editor_active(editor_id: int):
    editor = Editor.query.filter(Editor.id == editor_id).first()
    if not editor:
        raise Exception(f"Editor not found for id {editor_id}")
    editor.active = not editor.active
    db.session.add(editor)
    db.session.commit()
    return editor


@celery.task
def send_editor_assignments_notification():
    data = db.session.execute(
        """
        select 
        editor.name "Editor Name",
        concat('https://sellscale.retool.com/embedded/public/6b385d53-2d75-4bd1-979f-544d1dce8e13#campaign_uuid=', outbound_campaign.uuid) "Campaign Link",
        CARDINALITY(outbound_campaign.prospect_ids) "# of Messages",
        outbound_campaign.id campaign_id,
        outbound_campaign.editing_due_date,
        CONCAT(client_sdr.name, ' - ', client.company) "Client Name"
        from outbound_campaign
        left join editor on editor.id = outbound_campaign.editor_id
        left join client_sdr on client_sdr.id = outbound_campaign.client_sdr_id
        left join client on client.id = client_sdr.client_id
        where outbound_campaign.status = 'NEEDS_REVIEW'
        order by 
        1 desc;
    """
    ).fetchall()

    editor_assignments = {}
    for entry in data:
        editor_name = entry[0]
        campaign_link = entry[1]
        num_messages = entry[2]
        campaign_id = entry[3]
        editing_due_date = entry[4]
        client_name = entry[5]

        if editor_name not in editor_assignments:
            editor_assignments[editor_name] = []

        editor_assignments[editor_name].append(
            {
                "campaign_link": campaign_link,
                "num_messages": num_messages,
                "campaign_id": campaign_id,
                "editing_due_date": editing_due_date,
                "client_name": client_name,
            }
        )

    MIDDLE_BLOCKS = []
    for editor in editor_assignments:
        MIDDLE_BLOCKS.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*⚡️ Editor: " + editor + "*"},
            }
        )
        for campaign in editor_assignments[editor]:
            MIDDLE_BLOCKS.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"""*Campaign #{campaign['campaign_id']}* - {campaign['client_name']}\nDue by: {str(campaign['editing_due_date'])[0:10]}""",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": f"Click to edit {campaign['num_messages']} messages",
                            "emoji": True,
                        },
                        "value": "click_me_123",
                        "url": campaign["campaign_link"],
                        "action_id": "button-action",
                    },
                }
            )
        MIDDLE_BLOCKS.append({"type": "divider"})

    STARTING_BLOCKS = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*🚨 Daily campaign assignments reminder! 🚨 *",
            },
        },
        {"type": "divider"},
    ]

    ENDING_BLOCKS = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*<https://sellscale.retool.com/embedded/public/03223a6d-421d-4914-93ad-28117f4815f1|Show all campaign assignments in dashboard → >*",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Please edit these campaigns carefully before the assigned due date. Let a SellScale admin know ahead of time if you are not on track to complete your assignment.",
            },
        },
    ]

    send_slack_message(
        message="",
        webhook_urls=[URL_MAP["eng-sandbox"]],
        blocks=STARTING_BLOCKS + MIDDLE_BLOCKS + ENDING_BLOCKS,
    )
