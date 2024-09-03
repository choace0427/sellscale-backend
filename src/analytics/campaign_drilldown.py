import json
from app import db


def get_campaign_drilldown_data(archetype_id):
    sql = """
    SELECT
	prospect.id "prospect_id",
	prospect.full_name "prospect_name",
	CASE WHEN prospect_status_records.to_status IN ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION') THEN
		'ACTIVE_CONVO_SCHEDULING'
	WHEN prospect_email_status_records.to_status IN ('ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION') THEN
		'ACTIVE_CONVO_SCHEDULING'
	WHEN prospect_email_status_records.to_status IS NOT NULL THEN
		cast(prospect_email_status_records.to_status AS varchar)
	ELSE
		cast(prospect_status_records.to_status AS varchar)
	END "to_status",
	CASE WHEN prospect.icp_fit_score = 4 THEN
		'VERY HIGH'
	WHEN prospect.icp_fit_score = 3 THEN
		'HIGH'
	WHEN prospect.icp_fit_score = 2 THEN
		'MEDIUM'
	WHEN prospect.icp_fit_score = 1 THEN
		'LOW'
	WHEN prospect.icp_fit_score = 0 THEN
		'VERY LOW'
	ELSE
		'UNKNOWN'
	END "prospect_icp_fit_score",
	prospect.title "prospect_title",
	prospect.company "prospect_company",
	client_archetype.archetype "prospect_archetype",
	prospect.img_url "img_url",
	COALESCE(
		max(
			CASE WHEN prospect.li_last_message_from_prospect IS NOT NULL THEN
				prospect.li_last_message_from_prospect
			WHEN prospect_email.id IS NOT NULL
				AND prospect_email.outreach_status NOT IN ('SENT_OUTREACH', 'EMAIL_OPENED') THEN
				prospect_email.last_message
			ELSE
				'no response yet.'
			END
		),
		'no response yet.'
	) "last_message_from_prospect",
	max(
		CASE WHEN prospect_email.id IS NOT NULL
			AND prospect_email.outreach_status NOT IN ('SENT_OUTREACH', 'EMAIL_OPENED') THEN
			prospect_email.last_reply_time
		ELSE
			prospect.li_last_message_timestamp
		END) "last_message_timestamp"
FROM
	prospect
	JOIN client_archetype ON client_archetype.id = prospect.archetype_id
	LEFT JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id
	LEFT JOIN prospect_email ON prospect_email.prospect_id = prospect.id
	LEFT JOIN prospect_email_status_records ON prospect_email_status_records.prospect_email_id = prospect_email.id
WHERE (prospect_status_records.to_status IN ('SENT_OUTREACH', 'ACCEPTED', 'ACTIVE_CONVO', 'DEMO_SET', 'ACTIVE_CONVO_SCHEDULING', 'ACTIVE_CONVO_NEXT_STEPS', 'ACTIVE_CONVO_QUESTION')
	OR prospect_email_status_records.to_status IS NOT NULL)
AND prospect.archetype_id = :archetype_id
GROUP BY
	1,
	2,
	3,
	4,
	5,
	6,
	7,
	8
ORDER BY
	CASE WHEN prospect.li_last_message_timestamp IS NULL THEN
		1
	ELSE
		0
	END,
	li_last_message_timestamp DESC;
    """

    # Execute Query with parameters
    result = db.session.execute(sql, {"archetype_id": archetype_id})

    # Convert to list of dictionaries
    data = [dict(row) for row in result]

    return data
