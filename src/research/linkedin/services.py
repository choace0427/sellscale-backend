import requests
import json
import os

from .extractors.recommendations import get_recent_recommendation_summary

from .extractors.projects import get_recent_patent

from .extractors.experience import get_current_experience_description, get_list_of_past_jobs, get_years_of_experience, get_years_of_experience_at_current_job

from .extractors.current_company import get_current_company_description, get_current_company_specialties

from ..sample_research_response import SAMPLE_RESEARCH_RESPONSE

PROFILE_DETAILS_URL = "https://api.iscraper.io/v2/profile-details"
ISCRAPER_API_KEY = os.environ.get('ISCRAPER_API_KEY')

def research_personal_profile_details(profile_id: str):
    payload=json.dumps(
        {
            "profile_id":  profile_id,
            "profile_type": "personal",
            "contact_info": True,
            "recommendations": True,
            "related_profiles": True,
            "network_info": True
        }
    )
    headers = {
    'X-API-KEY': ISCRAPER_API_KEY,
    'Content-Type': 'application/json'
    }

    response = requests.request(
        "POST", 
        PROFILE_DETAILS_URL, 
        headers=headers, 
        data=payload
    )

    return json.loads(response.text)

def research_corporate_profile_details(company_name: str):
    payload=json.dumps(
        {
            "profile_id":  company_name,
            "profile_type": "company",
            "contact_info": True,
            "recommendations": True,
            "related_profiles": True,
            "network_info": True
        }
    )
    headers = {
    'X-API-KEY': ISCRAPER_API_KEY,
    'Content-Type': 'application/json'
    }

    response = requests.request(
        "POST", 
        PROFILE_DETAILS_URL, 
        headers=headers, 
        data=payload
    )

    return json.loads(response.text)

def get_research_payload(profile_id: str, test_mode: bool):
    if (test_mode):
        return SAMPLE_RESEARCH_RESPONSE

    personal_info = research_personal_profile_details(profile_id=profile_id)
    company_info = {}

    company_info = {}
    try:
        if len(personal_info.get('position_groups', [])) > 0:
            company_name = personal_info.get('position_groups', [])[0].get('company', {}).get('url', '').split('company/')[1].replace("/", "")
            company_info = research_corporate_profile_details(company_name=company_name)
    except:
        pass

    return {
        'personal': personal_info,
        'company': company_info
    }

def get_research_bullet_points(profile_id: str, test_mode: bool):
    info = get_research_payload(profile_id=profile_id, test_mode=test_mode)

    current_company_description = get_current_company_description(data=info)
    current_company_specialties = get_current_company_specialties(data=info)
    current_experience_description = get_current_experience_description(data=info)
    years_of_experience = get_years_of_experience(data=info)
    years_of_experience_at_current_job = get_years_of_experience_at_current_job(data=info)
    list_of_past_jobs = get_list_of_past_jobs(data=info)
    recent_patent = get_recent_patent(data=info)
    recent_recommendation = get_recent_recommendation_summary(data=info)

    bullets = {
        'current_company_description': current_company_description.get('response'),
        'current_company_specialties': current_company_specialties.get('response'),
        'current_experience_description': current_experience_description.get('response'),
        'years_of_experience': years_of_experience.get('response'),
        'years_of_experience_at_current_job': years_of_experience_at_current_job.get('response'),
        'list_of_past_jobs': list_of_past_jobs.get('response'),
        'recent_patent': recent_patent.get('response'),
        'recent_recommendation': recent_recommendation.get('response')
    }

    final_bullets = {}
    for key in bullets:
        if bullets[key]:
            final_bullets[key] = bullets[key].strip()

    return final_bullets

    # ✅  experience: years of experience in industry 
    # ✅  experience: years of experience at latest job 
    # ✅  experience: worked at X, Y, and Z in the past 
    
    # ✅  current job: ___________ is building the _____________ for ________ 
    # ✅  current job: came across <company> in the <industry> and saw your profile 
    # ✅  current job: <specialities> is such a hot topic these days! 
    
    #    skills: knows X languages: list
    #    skills: studied @ XYZ in _______
    #    skills: recent certificate in _________ X months ago
    #    skills: mention X, Y, Z skills - impressive!

    #    network: Knows X or Y at <current company>?
    #    network: was looking for professionals in _____ in <location>
    
    #    project: saw that you volunteer at ________
    #    project: saw your websites (blog | youtube | etc) - super cool!  // ( ex. jakob-sagatowski)
    #    project: saw you worked on project w/ __________
    # ✅ project: made patents in X, Y, Z
    
    # ✅ recommendation: saw ______'s recent recommendation of you. Looks like you're a _________ 


    
