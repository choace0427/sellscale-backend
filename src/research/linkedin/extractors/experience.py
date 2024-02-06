import math
import random
from datetime import datetime
from src.utils.abstract.attr_utils import deep_get
from src.ml.fine_tuned_models import get_completion
from src.ml.openai_wrappers import (
    wrapped_create_completion,
    OPENAI_COMPLETION_DAVINCI_3_MODEL,
)
from src.utils.converters.string_converters import sanitize_string, clean_company_name
from src.utils.datetime.dateutils import get_current_month, get_current_year


def get_current_experience_description(prospect_id: int, data: dict):
    # notice that you __________ at ________ currently

    company_name = deep_get(data, "company.details.name")
    title = sanitize_string(
        data.get("personal", {})
        .get("position_groups", [])[0]
        .get("profile_positions", [])[0]
        .get("title", "")
    )
    description = sanitize_string(
        data.get("personal", {})
        .get("position_groups", [])[0]
        .get("profile_positions", [])[0]
        .get("description", "")
    )

    description = description.replace(
        "\n", " "
    )  # We may eventually need to replace strange symbols as well

    raw_data = {
        "company_name": company_name,
        "title": title,
        "description": description,
    }

    instruction = 'You\'re writing a short sentence summary of an individual based on their job experience. Only include one sentence of the top 3 most impactful skills they have. Include the name of their company. Limit your summary to a maximum of 30 words. Use "they" and "their" to refer to the individual. Refer to their work in the present tense.'
    prompt = f"{instruction}\n\njob title: {raw_data['title']}\ncompany name: {raw_data['company_name']}\job description: {raw_data['description']}\n\nsummary: "

    if not company_name or not title or not description:
        response = ""
    else:
        response = wrapped_create_completion(
            model=OPENAI_COMPLETION_DAVINCI_3_MODEL, prompt=prompt, max_tokens=50
        )

    return {"raw_data": raw_data, "prompt": prompt, "response": response}


def get_years_of_experience(prospect_id: int, data: dict):
    # been in industry for X years

    positions = data.get("personal", {}).get("position_groups", [])
    current_year = datetime.now().year
    oldest_position_start = (
        positions[len(positions) - 1].get("date", {}).get("start")["year"]
    )
    newest_position_end = (
        positions[0].get("date", {}).get("end")["year"] or current_year
    )

    if not newest_position_end or not oldest_position_start:
        return {"response": ""}

    yoe = newest_position_end - oldest_position_start

    if yoe < 1:
        raw_data = {"years_of_experience": ""}
    else:
        if yoe == 1:
            raw_data = {"years_of_experience": "1 year of experience in industry"}
        elif yoe == 5:
            raw_data = {
                "years_of_experience": "Half a decade of experience in industry"
            }
        elif yoe == 10:
            raw_data = {"years_of_experience": "A decade of experience in industry"}
        else:
            raw_data = {
                "years_of_experience": str(yoe) + "+ years of experience in industry"
            }

    return {"raw_data": raw_data, "response": raw_data["years_of_experience"]}


def get_years_of_experience_at_current_job(prospect_id: int, data: dict):
    # been in current job for X years
    company_name = deep_get(data, "personal.position_groups.0.company.name")

    positions = deep_get(data, "personal.position_groups", [])
    newest_position = positions[0].get("date", {}).get("start")
    newest_month = newest_position["month"] or 1
    newest_year = newest_position["year"]

    current_month = get_current_month()
    current_year = get_current_year()

    months_at_job = current_month - newest_month
    years_at_job = current_year - newest_year
    time_at_job = (current_year - newest_year) + ((current_month - newest_month) / 12)

    # FIRST (fallback): Just give the raw numbers
    if math.floor(time_at_job) > 0:
        frame = "Spent {x} years at {company}.".format(
            x=math.floor(time_at_job), company=company_name
        )
    else:
        frame = "Spent {x} months at {company}.".format(
            x=math.ceil(12 * (time_at_job % 1)), company=company_name
        )

    # SECOND (mid-priority): Try to grab a colloquial phrase
    if time_at_job <= 0.4:  # Less than 5 months (5/12 ~ 0.417)
        frame = "Just started at {company}.".format(company=company_name)
    elif time_at_job > 0.4 and time_at_job < 0.6:  # 5-7 months
        frame = "Been at {company} for half a year.".format(company=company_name)
    elif time_at_job >= 0.6 and time_at_job < 0.84:  # 7-10 months:
        frame = "Been at {company} for over half a year.".format(company=company_name)
    elif time_at_job >= 40:  # 40+ years
        frame = "Been at {company} for over {time} decades.".format(
            company=company_name, time=math.floor(time_at_job // 10)
        )
    elif time_at_job >= 39:  # 39-40 years
        frame = "Been at {company} for nearly 4 decades.".format(company=company_name)
    elif time_at_job >= 30:  # 30-39 years
        frame = "Been at {company} for over 3 decades.".format(company=company_name)
    elif time_at_job >= 29:  # 29-30 years
        frame = "Been at {company} for nearly 3 decades.".format(company=company_name)
    elif time_at_job >= 20:  # 20-29 years
        frame = "Been at {company} for over 2 decades.".format(company=company_name)
    elif time_at_job >= 19:  # 19-20 years
        frame = "Been at {company} for nearly 2 decades.".format(company=company_name)
    elif time_at_job >= 10:  # 10-19 years
        frame = "Been at {company} for over a decade.".format(company=company_name)
    elif time_at_job >= 9:  # 9-10 years
        frame = "Been at {company} for nearly a decade.".format(company=company_name)
    elif time_at_job >= 5:  # 5-9 years
        frame = "Been at {company} for over half a decade.".format(company=company_name)
    elif time_at_job >= 2:  # 2-5 years
        frame = "Been at {company} for over {years} years.".format(
            company=company_name, years=math.floor(time_at_job)
        )
    elif time_at_job < 2 and time_at_job > 1.2:  # 14-24 months
        frame = "Been at {company} for over a year.".format(company=company_name)

    # THIRD (high priority): Check for anniversary
    if time_at_job % 1 > 0.9:
        frame = "{x}-year anniversary at {company} is coming up.".format(
            x=math.ceil(time_at_job), company=company_name
        )
    elif time_at_job % 1 < 0.15 and time_at_job >= 1:
        frame = "Had a recent {x}-year anniversary at {company}.".format(
            x=math.floor(time_at_job), company=company_name
        )

    if not company_name:
        frame = ""

    raw_data = {
        "current_month_year": "{month} / {year}".format(
            year=current_year, month=current_month
        ),
        "newest_month_year": "{month} / {year}".format(
            year=newest_year, month=newest_month
        ),
        "time_at_job": round(time_at_job, 2),
        "frame": frame,
    }

    return {"raw_data": raw_data, "response": frame}


def remove_suffixes_from_company_name(positions_str):
    """
    Remove suffixes from company name like "LLC" and "Inc."
    """
    replaced_suffixes = [
        " Inc",
        " Inc.",
        " LLC",
        " LLC.",
        " INC",
        " INC.",
        " Ltd",
        " .Ltd",
        " Co.",
        "®",
        " ®",
    ]
    replaced_suffixes.sort(key=lambda x: len(x), reverse=True)
    for suffix in replaced_suffixes:
        positions_str = positions_str.replace(suffix, "")
    return positions_str


def get_list_of_past_jobs(prospect_id: int, data: dict):
    # saw that you've worked at X, Y, Z
    position_data = deep_get(data, "personal.position_groups")
    past_positions = []
    current_positions = set()
    for position in position_data:
        if len(past_positions) >= 3:
            break

        company_name = clean_company_name(deep_get(position, "company.name"))
        start_date_year = deep_get(position, "date.start.year")
        start_date_month = deep_get(position, "date.start.month") or 1
        end_date_year = deep_get(position, "date.end.year")
        end_date_month = deep_get(position, "date.end.month") or 1

        # If company name exists in current_positions set (currently working there) or past_positions (duplicate), skip
        if company_name in current_positions or company_name in past_positions:
            continue

        # If no start date (undefined), skip
        if not start_date_year:
            continue

        # If not end date (current), skip and save as current job
        if not end_date_year:
            current_positions.add(company_name)
            continue

        # End date should be within the past 10 years
        if end_date_year < get_current_year() - 10:
            continue

        # Must have worked at least 1 year at the company.
        time_at_job = (end_date_year - start_date_year) + (
            (end_date_month - start_date_month) / 12
        )
        if time_at_job < 1:
            continue

        past_positions.append(company_name)

    # If no relevant positions, return empty dict
    if len(past_positions) == 0:
        return {}
    elif len(past_positions) == 1:
        response = "Has previously worked at {}".format(past_positions[0])
    elif len(past_positions) == 2:
        response = "Has previously worked at {} and {}".format(
            past_positions[0], past_positions[1]
        )
    else:
        response = "Has previously worked at {}, {} and {}".format(
            past_positions[0], past_positions[1], past_positions[2]
        )

    raw_data = {
        "positions": past_positions,
    }

    return {"raw_data": raw_data, "response": response}


def get_linkedin_bio_summary(prospect_id: int, data: dict):
    summary = deep_get(data, "personal.summary")
    if not summary:  # No bio
        return {"response": ""}

    first_name = deep_get(data, "personal.first_name")
    last_name = deep_get(data, "personal.last_name")
    if not first_name or not last_name:  # No name
        return {"response": ""}
    name = first_name + " " + last_name

    summary = summary.replace(
        "\n", " "
    )  # We may eventually need to replace strange symbols as well

    instruction = 'Summarize the individual\'s bio in 30 words or less. Use "they" and "their" to refer to the individual.'
    prompt = (
        f"individual: {name}\nbio: {summary}\n\ninstruction: {instruction}\n\nsummary:"
    )
    response = wrapped_create_completion(
        model=OPENAI_COMPLETION_DAVINCI_3_MODEL, prompt=prompt, max_tokens=35
    )

    return {"response": response.strip()}
