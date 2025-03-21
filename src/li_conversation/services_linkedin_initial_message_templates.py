from http.client import ACCEPTED
import re
from typing import Optional
from app import db, celery
from model_import import LinkedinInitialMessageTemplateLibrary, Client
from src.li_conversation.models import LinkedinInitialMessageTemplate
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.prospecting.models import ProspectOverallStatus


def create_new_linkedin_initial_message_template(
    name: str,
    raw_prompt: str,
    human_readable_prompt: str,
    length: str,
    transformer_blocklist: list,
    tone: str,
    labels: list,
):
    # only alphabets with hyphens all lowercase
    tag = re.sub(r"[^a-z-]", "", name.replace(" ", "-").lower()).replace(" ", "-")
    li_template: LinkedinInitialMessageTemplateLibrary = LinkedinInitialMessageTemplateLibrary(
        tag=tag,
        name=name,
        raw_prompt=raw_prompt,
        human_readable_prompt=human_readable_prompt,
        length=length,
        active=True,
        transformer_blocklist=transformer_blocklist,
        tone=tone,
        labels=labels,
    )
    db.session.add(li_template)
    db.session.commit()


def toggle_linkedin_initial_message_template_active_status(li_template_id: int):
    li_template: LinkedinInitialMessageTemplateLibrary = LinkedinInitialMessageTemplateLibrary.query.get(li_template_id)
    li_template.active = not li_template.active
    db.session.commit()


def update_linkedin_initial_message_template(
    li_template_id: int,
    name: str,
    raw_prompt: str,
    human_readable_prompt: str,
    length: str,
    transformer_blocklist: list,
    tone: str,
    labels: list,
):
    li_template: LinkedinInitialMessageTemplateLibrary = LinkedinInitialMessageTemplateLibrary.query.get(li_template_id)
    li_template.name = name
    li_template.raw_prompt = raw_prompt
    li_template.human_readable_prompt = human_readable_prompt
    li_template.length = length
    li_template.transformer_blocklist = transformer_blocklist
    li_template.tone = tone
    li_template.labels = labels
    db.session.commit()


def get_all_linkedin_initial_message_templates():
    frameworks = LinkedinInitialMessageTemplateLibrary.query.filter_by(active=True).all()

    return [bft.to_dict() for bft in frameworks]

def adjust_template_for_client(
    client_id: int,
    template_id: int
) -> str:
    client: Client = Client.query.get(client_id)
    template: LinkedinInitialMessageTemplateLibrary = LinkedinInitialMessageTemplateLibrary.query.get(template_id)

    client_company = client.company
    client_description = client.description

    template_raw_prompt = template.raw_prompt
    template_tone = template.tone

    adjustment_prompt = """Here is information about my company:
Company: {company_name}
Description: {company_description}

--------------
Here is a template I want to use:
"{template_raw_prompt}"

Template Tone: {template_tone}

-------------
Instruction: Adjust specific fields in this template to be better fit for our company.

Important Notes:
- keep the new template under 300 characters
- do not adjust too much; follow a similar structure and only customize the parts I mentioned.
- only alter the following fields:
1. [[ pain point ]]
2. [[ our company ]]
- Do NOT adjust any other fields like [[first name]] and [[title]] and [[colloquialized title]]
- keep the template tone and length the same
- do not deviate too much from the original template

-------------
New template:""".format(
        company_name=client_company,
        company_description=client_description,
        template_raw_prompt=template_raw_prompt,
        template_tone=template_tone
    )

    try: 
        completion = wrapped_chat_gpt_completion(
            messages=[
                {
                    'role': 'user',
                    'content': adjustment_prompt
                }
            ],
            model='gpt-4',
            max_tokens=200
        )

        cleaned_completion = completion.replace('"', '')

        return cleaned_completion
    except Exception as e:
        return template_raw_prompt

@celery.task(name="update_linkedin_initial_message_template_library")
def backfill_linkedin_initial_message_template_library_stats():
    # Fetch update data with provided SQL query
    fetch_query = """
    SELECT 
        li_init_template_id,
        COUNT(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'SENT_OUTREACH') AS new_times_used,
        COUNT(DISTINCT prospect.id) FILTER (WHERE prospect_status_records.to_status = 'ACCEPTED') AS new_times_accepted
    FROM generated_message
    JOIN prospect ON prospect.approved_outreach_message_id = generated_message.id
    JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id
    WHERE li_init_template_id IS NOT NULL
    GROUP BY li_init_template_id;
    """
    result = db.session.execute(fetch_query)
    data = result.fetchall()

    # Prepare data for bulk update
    update_data = [
        {
            'id': li_init_template_id,
            'times_used': new_times_used,
            'times_accepted': new_times_accepted
        } for li_init_template_id, new_times_used, new_times_accepted in data
    ]

    # Bulk update LinkedinInitialMessageTemplateLibrary
    db.session.bulk_update_mappings(LinkedinInitialMessageTemplate, update_data)

    # Commit changes
    db.session.commit()

    return True
