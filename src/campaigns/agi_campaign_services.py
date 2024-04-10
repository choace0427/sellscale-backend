import json
import yaml
from model_import import ClientSDR, Client, ClientArchetype, GeneratedMessageCTA
from app import db


def create_agi_campaign(
    client_sdr_id: int,
    query: str,
    campaign_instruction: str,
    run_prospecting: bool = True,
    run_linkedin: bool = True,
    run_email: bool = True,
):
    """
    Finds prospects and creates copy from a given request.

    Request example:
    Generate a new campaign targetting all product managers in the US, with a focus on the automotive industry.
    Offer them a free trial of our product.
    """
    from src.ml.openai_wrappers import wrapped_chat_gpt_completion
    from src.contacts.services import get_contacts_from_predicted_query_filters

    # pull all information from brain on rep, company
    rep: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id: int = rep.client_id
    client: Client = Client.query.get(client_id)

    rep_name = rep.name
    rep_title = rep.title
    company_name = client.company
    company_tagline = client.tagline
    company_description = client.description

    ctas = []
    linkedin_sequence = []
    email_sequence = []
    contacts = []
    top_cta_text_values = []

    print("Generating campaign name")
    campaign_name = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "system",
                "content": """
                Based on the request, give me a 3-7 word name for the campaign. 

                Examples:
                Input: "I want to target all product managers in the US, with a focus on the automotive industry. Offer them a free trial of our product."
                Output: "Automation Product Manager Free Trial"

                Input: "Let's focus on executives at Snapchat in the augmented reality division."
                Output: "Snapchat AR Executives"

                Important: 
                - Only return the name. No Yapping.
                - Don't add 'campaign' or 'targetting' or words like that. 
                - No quotations or special characters. Just the simple 3-7 word name.
                
                Request: {}
                Campaign Name:""".format(
                    query
                ),
            }
        ],
        model="gpt-4",
    )

    # make a new campaign
    print("Creating campaign")
    print("🔴 not implemented\n")

    # make a new segment
    print("Creating segment")
    print("🔴 not implemented\n")

    if run_prospecting:
        print("Finding contacts")
        contacts = get_contacts_from_predicted_query_filters(query=query)
        print("found contacts\n")

    if run_linkedin:
        # create linkedin campaign
        # get top CTAs from other people in the same company. Join on client archetype then client
        top_ctas_query = """
        with d as (
            select 
                generated_message_cta.text_value,
                count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') num_sent,
                count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') num_accepted
            from generated_message_cta
                join client_archetype on client_archetype.id = generated_message_cta.archetype_id
                join generated_message on generated_message.message_cta = generated_message_cta.id
                join prospect_status_records on prospect_status_records.prospect_id = generated_message.prospect_id
            where client_archetype.client_id = {}
            group by 1
        )
        select 
            text_value,
            num_sent,
            round(cast(num_accepted as float) / (num_sent + 0.0001) * 100) acceptance_rate
        from d
        where num_sent > 20
        order by 3 desc
        limit 10;
        """
        top_cta_text_values = db.session.execute(
            top_ctas_query.format(client_id)
        ).fetchall()

        # use with context to make CTAs
        print("Creating CTAs")
        new_ctas_prompt = """
        Here is information about the client:
        - Company Name: {company}
        - Company Tagline: {tagline}

        Here are some historical top CTAs that the client has used in the past:
        {top_ctas}

        Here is some information about the new campaign that you are creating:
        - Campaign Name: {campaign_name}
        - Rep Name: {rep_name}
        - Rep Title: {rep_title}
        - Prospect List Description: {query}
        - Campaign Instruction: {campaign_instruction}

        Return a JSON object with the following key and value:
        ctas: list[str]: A list of 2-4 Call to Actions (CTAs) that you would like to use in the new campaign.

        It should look like:
        {{
            "ctas": [
                "CTA 1",
                "CTA 2",
                "CTA 3"
            ]
        }}

        Ensure that the CTAs are less than 120 characters each and are relevant to the campaign. Use stylistic choices from the top CTAs.

        ONLY RETURN THE CTAs. NO YAPPING.

        Generate 2-4 CTAs only.

        CTAs:"""

        new_ctas = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "system",
                    "content": new_ctas_prompt.format(
                        company=company_name,
                        tagline=company_tagline,
                        top_ctas="\n".join(
                            ["- {}".format(cta[0]) for cta in top_cta_text_values]
                        ),
                        campaign_name=campaign_name,
                        rep_name=rep_name,
                        rep_title=rep_title,
                        query=query,
                        campaign_instruction=campaign_instruction,
                    ),
                }
            ],
            model="gpt-4",
            max_tokens=600,
        )

        ctas = yaml.safe_load(new_ctas)["ctas"]

        # make 3-4 step linkedin sequence and import steps in
        print("Creating linkedin sequence")

        sequence_prompt = """
        Here is information about the client:
        - Company Name: {company}
        - Company Tagline: {tagline}

        Here is information about the rep:
        - Rep Name: {rep_name}
        - Rep Title: {rep_title}

        Here is the campaign that you are creating:
        - Campaign Name: {campaign_name}
        - Prospect List Description: {query}
        - Campaign Instruction: {campaign_instruction}

        Here are some example sequences from top campaigns for {company}:
        {top_sequences}

        Return a JSON object with the following structure:
        - sequence: list[obj]
            - step: int: The step number in the sequence.
            - message: str: The template to send in the sequence.
            - title: str: The title of the sequence step

        An example of the structure is:
        {{
            "sequence": [
                {{
                    "step": 1,
                    "message": "Hello, I wanted to reach out to you about our new product.",
                    "title": "Introduction"
                }},
                ...
            ]
        }}

        Create a 3-4 step LinkedIn sequence for the campaign on behalf of {rep_name}. Use the stylistic choices from the top sequences.

        Important:
        - leverage context and personalization for the rep and the company in the messaging
        - ensure you are sticking with the goal of the campaign
        - be personalized and targetted towards the intended audience

        ONLY RETURN THE SEQUENCE. NO YAPPING.

        LinkedIn Sequence:"""

        top_sequences_query = """
        with d as (
            with top_sequences as (
                select 
                    client_archetype_id,
                    array_agg(
                        concat(
                            'step#',
                            bumped_count,
                            ' - ',
                            title,
                            ': "',
                            description,
                            '"'
                        )
                    ) sequence
                from bump_framework
                    join client_archetype on client_archetype.id = bump_framework.client_archetype_id
                where bump_framework.overall_status in ('ACCEPTED', 'BUMPED')
                    and bump_framework.default
                    and bump_framework.active
                    and client_archetype.client_id = 47
                group by 1
            )
            select 
                client_archetype.id,
                client_archetype.archetype,
                top_sequences.sequence,
                count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'SENT_OUTREACH') num_sent,
                count(distinct prospect_status_records.prospect_id) filter (where prospect_status_records.to_status = 'ACCEPTED') num_accepted
            from client_archetype
                join prospect on prospect.archetype_id = client_archetype.id 
                join prospect_status_records on prospect_status_records.prospect_id = prospect.id
                join top_sequences on top_sequences.client_archetype_id = client_archetype.id
            where client_archetype.client_id = {}
                and (not client_archetype.template_mode or client_archetype.template_mode is null)
            group by 1,2,3
        )
        select 
            id, archetype, sequence, num_sent, num_accepted, 
            cast(num_accepted as float) / num_sent acceptance_rate
        from d
        where num_sent > 20
        order by acceptance_rate desc;
        """

        top_sequences = db.session.execute(
            top_sequences_query.format(client_id)
        ).fetchall()

        top_sequences_text = "\n".join(
            [
                "- {}:\n{}".format(archetype, "\n".join(sequence))
                for _, archetype, sequence, _, _, _ in top_sequences
            ]
        )

        linkedin_sequence_str = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "system",
                    "content": sequence_prompt.format(
                        company=company_name,
                        tagline=company_tagline,
                        rep_name=rep_name,
                        rep_title=rep_title,
                        campaign_name=campaign_name,
                        query=query,
                        top_sequences=top_sequences_text,
                        campaign_instruction=campaign_instruction,
                    ),
                }
            ],
            model="gpt-4",
            max_tokens=1500,
        )

        linkedin_sequence = yaml.safe_load(linkedin_sequence_str)["sequence"]

        # create new review task for linkedin
        print("Creating review task for linkedin")
        print("🔴 not implemented\n")

    if run_email:
        # create 3 step email sequence
        email_sequence_prompt = """
        Here is information about the client:
        - Company Name: {company}
        - Company Tagline: {tagline}

        Here is information about the rep:
        - Rep Name: {rep_name}
        - Rep Title: {rep_title}

        Here is the campaign that you are creating:
        - Campaign Name: {campaign_name}
        - Request: {query}

        Return a JSON object with the following structure:
        - sequence: list[obj]
            - step: int: The step number in the sequence.
            - message: str: The template to send in the sequence. (ensure it's in HTML format)
            - title: str: The title of the sequence step

        An example of the structure is:
        {{
            "sequence": [
                {{
                    "step": 1,
                    "message": "Hello,<br/>I wanted to reach out to you about our new product.<br/>Best,<br/>[Rep Name]",
                    "title": "Introduction"
                }},
                ...
            ]
        }}

        Create a 3 step email sequence for the campaign on behalf of {rep_name}. Use the stylistic choices from the top sequences.

        Important:
        - leverage context and personalization for the rep and the company in the messaging
        - ensure you are sticking with the goal of the campaign
        - be personalized and targetted towards the intended audience

        ONLY RETURN THE SEQUENCE. NO YAPPING.

        Email Sequence:"""

        email_sequence_str = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "system",
                    "content": email_sequence_prompt.format(
                        company=company_name,
                        tagline=company_tagline,
                        rep_name=rep_name,
                        rep_title=rep_title,
                        campaign_name=campaign_name,
                        query=query,
                    ),
                }
            ],
            model="gpt-4",
            max_tokens=1500,
        )

        email_sequence = yaml.safe_load(email_sequence_str)["sequence"]

        # create new review task for email

    return {
        "contacts": contacts,
        "campaign_name": campaign_name,
        "metadata": {
            "rep_name": rep_name,
            "rep_title": rep_title,
            "company_name": company_name,
            "company_tagline": company_tagline,
            "company_description": company_description,
        },
        "linkedin": {
            "cta": {
                "ctas": ctas,
                "inspiration_ctas": [cta[0] for cta in top_cta_text_values],
            },
            "sequence": linkedin_sequence,
        },
        "email": {
            "sequence": email_sequence,
        },
    }
