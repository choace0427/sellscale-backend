from ....ml.fine_tuned_models import get_completion
from src.utils.converters.string_converters import sanitize_string
from src.ml.openai_wrappers import wrapped_create_completion, CURRENT_OPENAI_DAVINCI_MODEL


def get_current_company_description(data):
    # ___________ is building the _____________ for ________

    company_name = data.get("company", {}).get("details", {}).get("name")
    company_description = data.get("company", {}).get("details", {}).get("description")

    raw_data = {
        "company_name": company_name,
        "company_description": company_description,
    }

    if not company_name or not company_description:
        response = ""
        prompt = ""
    else: 
        company_description = company_description.strip().replace("\"", "\'")      
        prompt = f"company: {company_name}\n\nbio: {company_description}\n\ninstruction: Summarize what the company does in a short one-liner under 20 words in length.\n\ncompletion:"
        response = wrapped_create_completion(
            model=CURRENT_OPENAI_DAVINCI_MODEL,
            prompt=prompt,
            temperature=0.7,
            max_tokens=30
        )

    return {"raw_data": raw_data, "prompt": prompt, "response": response}


def get_current_company_specialties(data):
    # <specialities> is such a hot topic these days!

    company_name = data.get("company").get("details", {}).get("name")
    specialities = data.get("company", {}).get("details", {}).get("specialities", [])
    industries = data.get("company", {}).get("details", {}).get("industries", [])
    tagline = data.get("company", {}).get("details", {}).get("tagline")

    raw_data = {
        "company_name": company_name,
        "specialities": ", ".join(specialities),
        "industries": ", ".join(industries),
        "tagline": tagline,
    }

    prompt = "company: {company_name} -- specialities: {specialities} -- industries: {industries} -- tagline: {tagline}\n -- summary:".format(
        **raw_data
    )
    if not company_name or not specialities or not industries or not tagline:
        response = ""
    else:
        response = get_completion(
            bullet_model_id="recent_job_specialties", prompt=prompt
        )

    return {"raw_data": raw_data, "prompt": prompt, "response": response}
