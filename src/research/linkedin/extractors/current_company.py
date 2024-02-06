from ....ml.fine_tuned_models import get_completion
from src.utils.converters.string_converters import sanitize_string
from src.ml.openai_wrappers import (
    wrapped_create_completion,
    OPENAI_COMPLETION_DAVINCI_3_MODEL,
)


def get_current_company_description(prospect_id: int, data: dict):
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
        company_description = company_description.strip().replace('"', "'")
        prompt = f"company: {company_name}\n\nbio: {company_description}\n\ninstruction: Summarize what the company does in a short one-liner under 20 words in length.\n\ncompletion:"
        response = wrapped_create_completion(
            model=OPENAI_COMPLETION_DAVINCI_3_MODEL,
            prompt=prompt,
            temperature=0.65,
            max_tokens=30,
        )

    return {"raw_data": raw_data, "prompt": prompt, "response": response}


def get_current_company_specialties(prospect_id: int, data: dict):
    # <specialities> is such a hot topic these days!

    company_name = data.get("company").get("details", {}).get("name")
    specialities = data.get("company", {}).get("details", {}).get("specialities", [])

    raw_data = {
        "company_name": company_name,
        "specialities": ", ".join(specialities),
    }

    data = "company: {company_name} -- specialities: {specialities}".format(**raw_data)
    instruction = "Summarize what the company's focus is in a short one-liner under 20 words in length."
    prompt = "{data}\n\ninstruction: {instruction}\n\ncompletion:".format(
        data=data, instruction=instruction
    )
    if not company_name or not specialities:
        response = ""
    else:
        response = wrapped_create_completion(
            model=OPENAI_COMPLETION_DAVINCI_3_MODEL, prompt=prompt, max_tokens=35
        )

    return {"raw_data": raw_data, "prompt": prompt, "response": response}


def get_current_company_industry(prospect_id: int, data: dict):
    # ___________ works in the _____________ industry
    company_name = data.get("company", {}).get("details", {}).get("name")
    company_industries = data.get("company", {}).get("details", {}).get("industries")

    if len(company_industries) == 1:
        result = company_industries[0]
    elif len(company_industries) == 2:
        result = " and ".join(company_industries)
    else:
        result = ", ".join(company_industries[:-1]) + ", and " + company_industries[-1]

    result = f"{company_name} works in the {result.lower()} industry"

    return {"raw_data": {}, "prompt": "", "response": result}
