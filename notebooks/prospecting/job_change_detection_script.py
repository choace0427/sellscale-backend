from src.utils.slack import *
from app import db
from model_import import Client, ClientSDR, Prospect

# INPUTS
CLIENT_SDR_ID = 111

client_sdr: ClientSDR = ClientSDR.query.get(CLIENT_SDR_ID)
client: Client = Client.query.get(client_sdr.client_id)
webhook_url = client.pipeline_notifications_webhook_url
# webhook_url = URL_MAP["eng-sandbox"]

query = """
    with labeled_data as (
        with entries as (
            with d as (
                select 
                    prospect.id,
                    prospect.full_name,
                    prospect.linkedin_url,
                    research_payload.payload->'personal' "personal",
                    research_payload.payload->'company' "company",
                    research_payload.payload->'personal'->'position_groups'->0->'profile_positions' position_groups
                from prospect
                    join research_payload on prospect.id = research_payload.prospect_id
                where prospect.client_sdr_id = 111
                and research_payload.created_at > NOW() - '3 months'::INTERVAL
                    and prospect.overall_status = 'PROSPECTED'
            )
            select 
                id,
                full_name,
                linkedin_url,
                case when json_array_length(position_groups) > 1 then TRUE else FALSE end multiple_positions_at_current_company,
                extract(MONTH from NOW()) + extract(YEAR from NOW()) * 12 "current_months",
                cast(position_groups->0->'date'->'start'->>'month' as integer) + cast(position_groups->0->'date'->'start'->>'year' as integer) * 12 "last_change_months",
                position_groups->0->>'company' position_group_company,
                position_groups->0->>'title' position_group_title,
                position_groups->1->>'title' previous_position_title
            from d
        )
        select 
            case
                when entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then id
                when not entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then id
                else null
            end id,
            case
                when entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then full_name
                when not entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then full_name
                else null
            end full_name,
            case
                when entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then linkedin_url
                when not entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then linkedin_url
                else null
            end linkedin_url,
            case
                when entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then 'Recent Promotion'
                when not entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then 'Recent Job Change'
                else null
            end job_change,
            case
                when entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then concat('Was recently promoted from "', previous_position_title, '" to "', position_group_title, '" at ', position_group_company, ' ', current_months - last_change_months, ' months ago')
                when not entries.multiple_positions_at_current_company and (current_months - last_change_months < 3)
                    then concat('Recently joined ', position_group_company, ' as a "', position_group_title, '" ', current_months - last_change_months, ' months ago')
                else ''
            end custom_data,
            position_group_company,
            position_group_title,
            previous_position_title,
            current_months - last_change_months months_since_last_change
        from entries
        order by random()
    )
    select *
    from labeled_data;
""".format(
    client_sdr_id=CLIENT_SDR_ID
)

data = db.session.execute(query).fetchall()

print(data)

# num_job_changes = 0
# job_change_ids = []
num_promotions = 0
promotion_ids = []
promo_map = {}
for row in data:
    if row.job_change == "Recent Promotion":
        num_promotions += 1
        promotion_ids.append(row.id)
        promo_map[row.id] = {
            "previous_position_title": row.previous_position_title,
            "position_group_title": row.position_group_title,
            "position_group_company": row.position_group_company,
            "months_since_last_change": row.months_since_last_change,
        }
    # if row.job_change == "Recent Job Change":
    #     num_job_changes += 1
    #     job_change_ids.append(row.id)

print("Sending notification to " + webhook_url)
message = "Recent Job Change Detected"
print(message)

# print("Found " + str(num_job_changes) + " job changes")
print("Found " + str(num_promotions) + " promotions")

# if num_job_changes > 0:
#     print("Found " + str(num_job_changes) + " job changes")
#     example_profiles = [Prospect.query.get(i) for i in job_change_ids[:3]]
#     for profile in example_profiles:
#         print(profile.full_name, ' - ', profile.linkedin_url)

print("Found " + str(num_promotions) + " promotions")
example_profiles = [Prospect.query.get(i) for i in promotion_ids[:3]]
for profile in example_profiles:
    print(profile.full_name, " - ", profile.linkedin_url)
    print(promo_map[profile.id])


promotion_details = "\n".join(
    [
        f"> *<https://{profile.linkedin_url}|{profile.full_name}>* @ *{profile.company}*\n>_{promo_map[profile.id]['previous_position_title']} → {promo_map[profile.id]['position_group_title']}_\n>{promo_map[profile.id]['months_since_last_change']} month{'s' if promo_map[profile.id]['months_since_last_change'] > 1 else ''} ago\n"
        for profile in example_profiles
    ]
)

# Slack message blocks
blocks = [
    {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Triggers: 🪜 Recent Promotions Detected",
            "emoji": True,
        },
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"Detected *{str(num_promotions)} promotions* from your prospect list.",
        },
    },
    {"type": "section", "text": {"type": "mrkdwn", "text": promotion_details}},
]

if num_promotions > 3:
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"and *{num_promotions - 3} other prospects* have been added to your outbound campaign.",
            },
        }
    )

# Send the Slack message
result = send_slack_message(
    message="Recent Promotions Notification",
    webhook_urls=[webhook_url],
    blocks=blocks,
)
