from app import db


# Function to fetch rejection analysis data for NOT_INTERESTED or NOT_QUALIFIED prospects
def get_rejection_analysis_data(client_sdr_id, status):
    # SQL query to retrieve disqualification reasons and counts
    query = """
        SELECT 
            CASE
                WHEN prospect.disqualification_reason IS NULL THEN 'n/a'
                WHEN prospect.disqualification_reason ILIKE '%OTHER -%' THEN 'Other'
                ELSE prospect.disqualification_reason
            END,
            COUNT(DISTINCT prospect.id)
        FROM prospect
            JOIN prospect_status_records ON prospect_status_records.prospect_id = prospect.id
        WHERE 
            prospect_status_records.to_status = :status
            AND prospect.status IN ('NOT_INTERESTED', 'NOT_QUALIFIED')
            AND prospect.client_sdr_id = :client_sdr_id
            AND disqualification_reason IS NOT NULL
        GROUP BY 1
        ORDER BY 2 DESC;
    """
    # Executing the query with provided parameters
    results = db.session.execute(
        query, {"client_sdr_id": client_sdr_id, "status": status}
    ).fetchall()
    # Formatting the results for response
    return [{"category": row[0], "value": row[1]} for row in results]


# Function to fetch detailed information of prospects that are either 'NOT_INTERESTED' or 'NOT_QUALIFIED'.
def get_rejection_report_data(client_sdr_id):
    # SQL query to retrieve rejection report data points
    query = """
    SELECT 
        prospect.company AS "Company",
        prospect.title AS "Title",
        prospect.full_name AS "Full Name",
        prospect.linkedin_url AS "Linkedin URL",
        prospect.img_url AS "Prospect Img",
        client_archetype.emoji AS "Emoji",
        client_archetype.archetype AS "Campaign",
        client_archetype.id AS "Campaign ID",
        prospect.disqualification_reason AS "Disqualification Reason"
        FROM prospect
        JOIN client_archetype ON client_archetype.id = prospect.archetype_id
        WHERE 
            prospect.status IN ('NOT_INTERESTED', 'NOT_QUALIFIED')
            AND prospect.client_sdr_id = :client_sdr_id
            AND prospect.disqualification_reason IS NOT NULL;
    """
    # Executing the query with provided parameters
    results = db.session.execute(query, {"client_sdr_id": client_sdr_id}).fetchall()
    # Formatting the results for response
    return [dict(row) for row in results]
