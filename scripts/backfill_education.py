exec(
    '''
from model_import import Prospect, Client
from app import db
from tqdm import tqdm

update_query = """
WITH EducationData AS (
    SELECT 
        prospect.id,
        research_payload.payload->'personal'->'education'->0->'school'->>'name' AS new_education_1,
        research_payload.payload->'personal'->'education'->1->'school'->>'name' AS new_education_2
    FROM prospect
    JOIN research_payload ON research_payload.prospect_id = prospect.id
    	and prospect.education_1 is null
    	and prospect.client_id = {client_id}
    LIMIT 10000
)
UPDATE prospect
SET 
    education_1 = EducationData.new_education_1,
    education_2 = EducationData.new_education_2
FROM EducationData
WHERE prospect.id = EducationData.id;
"""


def backfill_education():
    clients = Client.query.all()

    for client in tqdm(clients):
        result = db.session.execute(update_query.format(client_id=client.id))
        db.session.commit()

        print(f"Updated {result.rowcount} rows for client {client.id}")
'''
)
