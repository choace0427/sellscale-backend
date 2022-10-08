from datetime import datetime

from ....utils.abstract.attr_utils import deep_get
from ....ml.fine_tuned_models import get_completion
import math
import random


def get_current_experience_description(data):
    # notice that you __________ at ________ currently

    company_name = data.get("company").get("details", {}).get("name")
    title = (
        data.get("personal", {})
        .get("position_groups", [])[0]
        .get("profile_positions", [])[0]
        .get("title", "")
    )
    description = (
        data.get("personal", {})
        .get("position_groups", [])[0]
        .get("profile_positions", [])[0]
        .get("description", "")
    )

    raw_data = {
        "company_name": company_name,
        "title": title,
        "description": description,
    }

    prompt = "company: {company_name} -- description: {description} -- title: {title}\n -- summary:".format(
        **raw_data
    )
    if not company_name or not title or not description:
        response = ""
    else:
        response = get_completion(
            bullet_model_id="current_experience_description", prompt=prompt
        )

    return {"raw_data": raw_data, "prompt": prompt, "response": response}


def get_years_of_experience(data):
    # been in industry for X years

    positions = data.get("personal", {}).get("position_groups", [])
    oldest_position = positions[len(positions) - 1].get("date", {}).get("start")["year"]
    newest_position = positions[0].get("date", {}).get("start")["year"]

    if not newest_position or not oldest_position:
        raw_data = {"years_of_experience": ""}
    else:
        raw_data = {
            "years_of_experience": str(newest_position - oldest_position)
            + "+ years of experience in industry"
        }

    return {"raw_data": raw_data, "response": raw_data["years_of_experience"]}


def get_years_of_experience_at_current_job(data):
    # been in current job for X years
    company_name = data.get("company").get("details", {}).get("name")

    positions = data.get("personal", {}).get("position_groups", [])
    newest_position = positions[0].get("date", {}).get("start")
    newest_month = newest_position["month"] or 1
    newest_year = newest_position["year"]

    current_month = datetime.now().month
    current_year = datetime.now().year

    months_at_job = current_month - newest_month
    years_at_job = current_year - newest_year
    time_at_job = (current_year - newest_year) + ((current_month - newest_month) / 12)

    if time_at_job % 1 > 0.9:
        frame = "Your {x} year anniversary at {company} is right around the corner! Kudos".format(
            x=math.ceil(time_at_job), company=company_name
        )
    elif time_at_job % 1 > 0.8:
        frame = "Noticed that you're coming up on {x} years at {company}. Early congratulations!".format(
            x=math.ceil(time_at_job), company=company_name
        )
    elif time_at_job % 1 < 0.3 and years_at_job > 0:
        frame = "Congrats on your recent {x} year anniversary at {company}. Congratulations!".format(
            x=math.floor(time_at_job), company=company_name
        )
    elif time_at_job % 1 < 0.15 and years_at_job > 0:
        frame = "{x} year anniversary at {company}. What a run - congrats!".format(
            x=math.floor(time_at_job), company=company_name
        )
    elif years_at_job == 0:
        frame = "Spent {x} months at {company}".format(
            x=round(months_at_job, 1), company=company_name
        )
    else:
        frame = "Spent {x} years at {company}".format(
            x=round(years_at_job, 1), company=company_name
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


def get_list_of_past_jobs(data):
    # saw that you've worked at X, Y, Z
    position_data = deep_get(data, "personal.position_groups")
    positions = [deep_get(x, "company.name") for x in position_data][1:][0:3]
    positions_str = ", ".join(positions)

    raw_data = {
        "positions": positions,
    }

    prob = random.random()
    if prob > 0.8:
        response = "Saw that they've worked at {} in the past".format(positions_str)
    elif prob > 0.6:
        response = "Loved following journey between {}".format(positions_str)
    elif prob > 0.4:
        response = "Has a trove of experiences at {}".format(positions_str)
    elif prob > 0.2:
        response = "Kudos on all the experiences at {}".format(positions_str)
    else:
        response = "Has worked at {}".format(positions_str)

    return {"raw_data": raw_data, "response": response}
