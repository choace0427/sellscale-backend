from src.ml.services import get_text_generation
from src.prospecting.models import Prospect
from src.prospecting.services import (
    create_prospect_from_linkedin_link,
    get_linkedin_slug_from_url,
)
from src.research.linkedin.services import get_research_and_bullet_points_new
from src.research.models import ResearchPayload, ResearchPoints
from ..utils.abstract.attr_utils import deep_get
from src.ml.openai_wrappers import *
import requests
from bs4 import BeautifulSoup
from app import db

CLIENT_ID = 38  # SellScale Scribe client
CLIENT_ARCHETYPE_ID = 268  # SellScale Scribe archetype
CLIENT_SDR_ID = 89  # SellScale Scribe SDR


def get_indiduals_prospect_id_from_linkedin_url(input_linkedin_url):
    linkedin_slug = get_linkedin_slug_from_url(input_linkedin_url)
    prospect = (
        Prospect.query.filter(Prospect.linkedin_url.ilike("%" + linkedin_slug + "%"))
        .filter(Prospect.client_id == CLIENT_ID)
        .first()
    )
    if prospect:
        return prospect.id
    prospect_id = None
    if prospect:
        prospect_id = prospect.id
    else:
        success, prospect_id = create_prospect_from_linkedin_link(
            archetype_id=CLIENT_ARCHETYPE_ID,
            url=input_linkedin_url,
            synchronous_research=True,
            allow_duplicates=False,
        )
        prospect = Prospect.query.filter_by(id=prospect_id).first()
        prospect.linkedin_url = "linkedin.com/in/" + linkedin_slug
        db.session.add(prospect)
        db.session.commit()


def get_summary_from_website(url, max_retries=3):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")

            # Extract website description
            meta_description = soup.find("meta", {"name": "description"})
            website_description = (
                meta_description.get("content").strip()
                if meta_description
                else "Description not found"
            )

            # Extract company name
            company_name = (
                soup.find("title").get_text().strip()
                if soup.find("title")
                else "Title not found"
            )
        else:
            print("Failed to retrieve the page:", response.status_code)

        completion = get_text_generation(
            [
                {
                    "role": "user",
                    "content": "Here is a bunch of HTML data from a website: \n"
                    + str(html_content[0:3700])
                    + "===========\nExtract the name of the company and a description of what they do value props and mission statement from the website. Format it like this exactly and infer details when needed: \nName: COMPANY NAME\nDescription: COMPANY DESCRIPTION\nValue Props: BULLET POINT LIST OF VALUE PROPS\nMission Statement: <mission statement based on relevant details>",
                }
            ],
            model="gpt-4",
            max_tokens=300,
            type="MISC_SUMMARIZE",
        )
        return completion
    except requests.RequestException as e:
        if max_retries > 0:
            print("Retrying website extraction..." + str(e))
            return get_summary_from_website(url, max_retries - 1)


def determine_persona_from_prospect_ids(prospect_ids):
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_ids)
    ).all()
    titles = [prospect.title for prospect in prospects]

    completion = get_text_generation(
        [
            {
                "role": "user",
                "content": "Here are the titles of the prospects: \n"
                + str(titles)
                + "\n\nDetermine the persona of the prospects based on their titles. It should be a short title and less than 6 words long. Only generate ONE persona that's a summary of inputted people: \nPersona:",
            }
        ],
        model="gpt-4",
        max_tokens=20,
        type="MISC_CLASSIFY",
    )

    return completion


def determine_icp_filters(prospect_ids, company_description):
    prospects = Prospect.query.filter(Prospect.id.in_(prospect_ids)).all()

    def get_blurb_for_prospect(prospect: Prospect):
        blurb = ""
        if prospect.title is not None:
            blurb += "Title: " + prospect.title + "\n"
        if prospect.employee_count is not None:
            blurb += "Employee Count: " + str(prospect.employee_count) + "\n"
        if prospect.industry is not None:
            blurb += "Industry: " + prospect.industry + "\n"
        blurb += "\n"

    blurbs = [get_blurb_for_prospect(prospect) for prospect in prospects]

    completion = get_text_generation(
        [
            {
                "role": "user",
                "content": "Here is the company description: \n"
                + company_description
                + "\n\n Here are a couple sample ideal prospects. Use this list as inspiration when determining a list of prospects to outreach to: \n"
                + str(blurbs)
                + "\n\nDetermine the ICP filters for the prospects based on their titles. Each set of filters should be comma separated in this format:\n----\nTitles: < comma separated list of titles >\nEmployee Count: < comma separated list of employee counts >\nIndustry: < comma separated list of industries >\nKeywords: < comma separated list of keywords >\nLocation: United States\n----\nICP Filters:",
            }
        ],
        model="gpt-4",
        max_tokens=300,
        type="ICP_CLASSIFY",
    )

    return completion


def make_sample_ctas(persona, website_summary):
    list_of_sample_ctas = [
        "I’d love to chat more about how you are operating the back-office at your facility.",
        "Let's find some time to chat about compensation benchmarking?",
        "I work in PropTech and am curious - how do you all currently engage your renter leads?",
        "Saw you’ve explored outdoor advertising in the past. We’ve launched a new solution in outdoor ad attribution - would love to connect.",
        "Since you’re a leader in your health system, would love to see if Curative is helpful for physician staffing.",
    ]
    completion = get_text_generation(
        [
            {
                "role": "user",
                "content": "Here is the persona: \n"
                + persona
                + "\n\nHere is the website summary of the company I am reaching out on behalf of: \n"
                + website_summary
                + "\n\nMake 3 sample CTAs for the listed company reaching out to the persona. Each CTA should be a short sentence and use these CTAs as inspiration:\n:"
                + "\n- ".join(list_of_sample_ctas)
                + "\n\nSample CTAs:",
            }
        ],
        model="gpt-4",
        max_tokens=300,
        type="LI_CTA",
    )

    return completion


def generate_onboarding(url, sample_prospects):
    print(
        "Building a new SellScale profile from the following information:\n- Website: "
        + url
        + "\n"
        + "- Prospects: "
        + str(sample_prospects)
        + "\n\n"
    )

    # Gather website details
    print("Getting website summary...")
    website_summary = get_summary_from_website(url)
    print("-------\nWebsite summary: " + website_summary + "\n---------")

    # Gather Prospect Details
    print("\n\nGetting prospect IDs...")
    prospect_ids = [
        get_indiduals_prospect_id_from_linkedin_url(prospect)
        for prospect in sample_prospects
    ]
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.id.in_(prospect_ids)
    ).all()
    print("---------\nProspect IDs: " + str(prospect_ids) + "\n---------")

    # Determine persona
    print("\n\nDetermining persona...")
    persona = determine_persona_from_prospect_ids(prospect_ids)
    print("---------\nPersona:" + persona + "\n---------")

    # Determine ICP Fitlers
    print("\n\nDetermining ICP Filters...")
    icp_filters = determine_icp_filters(prospect_ids, website_summary)
    print("---------\nICP Filters:\n" + icp_filters + "\n---------")

    # Prepare linkedin CTAs
    print("\n\nPreparing sample CTAs for Linkedin outreach...")
    sample_ctas = make_sample_ctas(persona, website_summary)
    print("---------\nSample CTAs:\n" + sample_ctas + "\n---------")

    return {
        "website_summary": website_summary,
        "prospect_ids": prospect_ids,
        "persona": persona,
        "icp_filters": icp_filters,
        "sample_ctas": sample_ctas,
        "prospects": [p.to_dict() for p in prospects],
    }
