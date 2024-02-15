from model_import import Prospect, ClientSDR, ResearchPayload
from src.research.models import (
    ResearchPointType,
    ResearchType,
    ResearchPoints,
)
from src.research.linkedin.services import get_research_payload_new
from src.research.services import get_all_research_point_types, get_research_point_type
from src.research.linkedin.extractors.experience import (
    get_current_experience_description,
    get_linkedin_bio_summary,
    get_list_of_past_jobs,
    get_years_of_experience,
    get_years_of_experience_at_current_job,
)
from src.research.linkedin.extractors.location import get_current_location
from src.research.linkedin.extractors.education import (
    get_common_education,
)
from src.research.linkedin.extractors.projects import get_recent_patent
from src.research.linkedin.extractors.recommendations import (
    get_recent_recommendation_summary,
)
from src.research.website.general_website_transformer import (
    generate_general_website_research_points,
)
from src.research.linkedin.extractors.current_company import (
    get_current_company_description,
    get_current_company_industry,
    get_current_company_specialties,
)
from src.research.linkedin.extractors.custom_data import get_custom_research
from app import db


def generate_research_points(prospect_id: int, test_mode: bool = False):
    """
    Generates research points for a prospect based on the prospect's research payloads
    and the research point types the prospect's sdr has active.
    """

    prospect: Prospect = Prospect.query.get(prospect_id)
    client_sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)

    # Populate the research payload if it hasn't been already
    get_research_payload_new(prospect_id=prospect_id, test_mode=test_mode)

    # Get general prospect the research payload
    payload = ResearchPayload.get_by_prospect_id(
        prospect_id=prospect_id, payload_type=ResearchType.LINKEDIN_ISCRAPER
    )

    final_research_points = []

    try:
        # We generate all the points (including ones a blocklist) because they're filtered later
        for research_point_type in get_all_research_point_types(
            client_sdr.id, archetype_id=prospect.archetype_id
        ):
            # If is custom, use corresponding custom payload
            if research_point_type.get("client_id"):
                payload: ResearchPayload = ResearchPayload.query.filter(
                    ResearchPayload.prospect_id == prospect_id,
                    ResearchPayload.research_type == ResearchType.CUSTOM_DATA,
                    ResearchPayload.research_sub_type
                    == research_point_type.get("name"),
                ).first()

            if payload is None:
                continue

            # If the research point already exists, we append it
            research_point: ResearchPoints = ResearchPoints.query.filter(
                ResearchPoints.research_payload_id == payload.id,
                ResearchPoints.research_point_type == research_point_type.get("name"),
            ).first()
            if research_point:
                final_research_points.append(research_point.to_dict())
                continue

            # Else we create it

            # Execute the function associated with the research point type
            result = execute_research_point_type(
                research_point_type.get("name"), prospect_id, payload.payload
            )
            text: str = result.get("response", "")
            if text.strip() == "":
                continue

            # Create the research point
            research_point: ResearchPoints = ResearchPoints(
                research_payload_id=payload.id,
                research_point_type=research_point_type.get("name"),
                value=text.strip(),
            )
            db.session.add(research_point)
            db.session.commit()

            final_research_points.append(research_point.to_dict())

    except Exception as e:
        db.session.rollback()
        raise e

    return final_research_points

    # Support this?
    #       client: Client = Client.query.get(prospect.client_id)
    #       if client.id == 9:  # TODO only run for AdQuick for now
    #           print("Running SERP Extractor for AdQuick")
    #           serp_extractor = SerpNewsExtractorTransformer(prospect_id=prospect_id)
    #           serp_extractor.run()


##############################
# REGISTER TRANSFORMERS HERE #
##############################
# Define what research point types call what functions
# - function must return a dict with at least the key "response" -> str
# - function must have args (prospect_id: int, payload: dict)
TRANSFORMERS_MAP = {
    "get_current_company_description": {
        "function": get_current_company_description,
    },
    "get_current_company_specialties": {
        "function": get_current_company_specialties,
    },
    "get_current_experience_description": {
        "function": get_current_experience_description,
    },
    "get_years_of_experience": {
        "function": get_years_of_experience,
    },
    "get_current_location": {
        "function": get_current_location,
    },
    "get_years_of_experience_at_current_job": {
        "function": get_years_of_experience_at_current_job,
    },
    "get_list_of_past_jobs": {
        "function": get_list_of_past_jobs,
    },
    "get_recent_patent": {
        "function": get_recent_patent,
    },
    "get_recent_recommendation_summary": {
        "function": get_recent_recommendation_summary,
    },
    "generate_general_website_research_points": {
        "function": generate_general_website_research_points,
    },
    "get_linkedin_bio_summary": {
        "function": get_linkedin_bio_summary,
    },
    "get_common_education": {
        "function": get_common_education,
    },
    "get_current_company_industry": {
        "function": get_current_company_industry,
    },
    "get_custom_research": {
        "function": get_custom_research,
    },
}
###############################


def execute_research_point_type(
    type_name: str, prospect_id: int, payload: dict
) -> dict:
    """
    Executes the function associated with the research point type
    Returns: dict = {"response": str}
    """

    research_point_type = get_research_point_type(type_name)
    try:
        transformer = TRANSFORMERS_MAP.get(research_point_type.get("function_name"))
        if transformer:
            return transformer.get("function")(prospect_id, payload)
        else:
            return {"response": ""}
    except:
        return {"response": ""}
