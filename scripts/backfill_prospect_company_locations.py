exec(
    '''
from sqlalchemy import update
from app import db
from model_import import Prospect

while True:
    # Check if there are prospects to update
    count_query = """
    SELECT COUNT(*)
    FROM prospect
    WHERE prospect_location is NULL AND company_location is NULL;
    """
    count_result = db.session.execute(count_query).scalar()
    if count_result == 0:
        break  # Exit loop if no prospects need updating

    # SQL query string
    sql_query = """
    SELECT 
        prospect.id as prospect_id,
        CONCAT(
            CASE WHEN research_payload.payload->'personal'->'location'->>'city' IS NOT NULL THEN CONCAT(research_payload.payload->'personal'->'location'->>'city', ', ') ELSE '' END,
            CASE WHEN research_payload.payload->'personal'->'location'->>'state' IS NOT NULL THEN CONCAT(research_payload.payload->'personal'->'location'->>'state', ', ') ELSE '' END,
            CASE WHEN research_payload.payload->'personal'->'location'->>'country' IS NOT NULL THEN CONCAT(research_payload.payload->'personal'->'location'->>'country', ', ') ELSE '' END
        ) as prospect_location,
        CONCAT(
            CASE WHEN research_payload.payload->'company'->'details'->'locations'->'headquarter'->>'city' IS NOT NULL THEN CONCAT(research_payload.payload->'company'->'details'->'locations'->'headquarter'->>'city', ', ') ELSE '' END,
            CASE WHEN research_payload.payload->'company'->'details'->'locations'->'headquarter'->>'geographicArea' IS NOT NULL THEN CONCAT(research_payload.payload->'company'->'details'->'locations'->'headquarter'->>'geographicArea', ', ') ELSE '' END,
            CASE WHEN research_payload.payload->'company'->'details'->'locations'->'headquarter'->>'country' IS NOT NULL THEN CONCAT(research_payload.payload->'company'->'details'->'locations'->'headquarter'->>'country', ', ') ELSE '' END
        ) as company_location
    FROM prospect
    JOIN research_payload ON research_payload.prospect_id = prospect.id
    WHERE prospect.prospect_location IS NULL AND prospect.company_location IS NULL
    ORDER BY RANDOM()
    LIMIT 1000;
    """

    # Execute the SQL query
    results = db.session.execute(sql_query).fetchall()

    # Check if results were returned
    if not results:
        break  # Exit loop if no more prospects to update

    # Prepare data for bulk update
    update_data = [{'id': row.prospect_id, 
                    'prospect_location': row.prospect_location.rstrip(', '), 
                    'company_location': row.company_location.rstrip(', ')} 
                   for row in results]

    # Perform bulk update
    for data in update_data:
        db.session.execute(
            update(Prospect).where(Prospect.id == data['id']).values(
                prospect_location=data['prospect_location'],
                company_location=data['company_location']
            )
        )

    print(f'Updated {len(update_data)} prospects')

    # Commit the changes
    db.session.commit()

'''
)
