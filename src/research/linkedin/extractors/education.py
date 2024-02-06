from model_import import ClientSDR, Prospect
from src.utils.abstract.attr_utils import deep_get


def get_common_education(prospect_id: int, data: dict) -> dict:
    """Gets the common education between a prospect and an SDR, if there is one.

    Args:
        data (dict): LinkedIn payload
        client_sdr_id (int): ID of the SDR

    Returns:
        dict: Response to be sent to create research point
    """
    prospect: Prospect = Prospect.query.get(prospect_id)
    sdr: ClientSDR = ClientSDR.query.get(prospect.client_sdr_id)
    if not sdr:
        return {"response": ""}

    questionnaire = sdr.questionnaire
    if not questionnaire:
        return {"response": ""}

    prospect_education_list = deep_get(data, "personal.education")
    if not prospect_education_list:
        return {"response": ""}

    # Construct SDR education map, will be used.
    sdr_education_map = {}
    for sdr_education in sdr.questionnaire.get("education", []):
        sdr_school = sdr_education.get("name")
        sdr_start_date = sdr_education.get("year_started")
        sdr_end_date = sdr_education.get("year_ended")
        # Other fields can be added in the future
        sdr_education_map[sdr_school] = {
            "start_date": sdr_start_date,
            "end_date": sdr_end_date,
        }

    for prospect_education in prospect_education_list:
        school = deep_get(prospect_education, "school.name")
        start_date = deep_get(prospect_education, "date.start.year")
        end_date = deep_get(prospect_education, "date.end.year")

        if not school:
            continue

        # Both attended the same school
        if school in sdr_education_map:
            sdr_education = sdr_education_map[school]

            # Make prospect string
            prospect_full_name = (
                deep_get(data, "personal.first_name")
                + " "
                + deep_get(data, "personal.last_name")
            )
            prospect_education_string = f"{prospect_full_name} attended {school}"
            if start_date and end_date:
                prospect_education_string = (
                    f"{prospect_education_string} from {start_date} to {end_date}"
                )

            # Make SDR string
            sdr_education_string = f"I attended {school}"
            sdr_start_date = sdr_education.get("start_date")
            sdr_end_date = sdr_education.get("end_date")
            if sdr_start_date and sdr_end_date:
                sdr_education_string = (
                    f"{sdr_education_string} from {sdr_start_date} to {sdr_end_date}"
                )

            # Return response. Short circuit.
            return {"response": f"{prospect_education_string}. {sdr_education_string}."}

    return {"response": ""}
