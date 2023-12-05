from model_import import Prospect
from tqdm import tqdm
from src.prospecting.services import (
    extract_colloquialized_company_name,
    extract_colloquialized_prospect_title,
)

prospects = Prospect.query.filter(Prospect.colloquialized_title == None).all()

for prospect in tqdm(prospects):
    extract_colloquialized_prospect_title.delay(prospect.id)
    extract_colloquialized_company_name.delay(prospect.id)
