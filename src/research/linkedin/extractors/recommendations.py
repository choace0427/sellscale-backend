from datetime import datetime

from ....ml.fine_tuned_models import get_completion

from ....utils.abstract.attr_utils import deep_get


def get_recent_recommendation_summary(data):
    # saw _______'s recommendation of you. Seems like _________

    recommender_name = deep_get(data, "personal.recommendations.0.first_name", "")
    recommendation = deep_get(data, "personal.recommendations.0.text", "")
    created_at = deep_get(data, "personal.recommendations.0.created_at")
    years_since_recommendation = (
        datetime.now() - datetime.fromisoformat(created_at)
    ).days / 365

    if not recommender_name or not recommendation or years_since_recommendation > 5:
        return {}

    raw_data = {"recommender_name": recommender_name, "recommendation": recommendation}

    prompt = "recommender_name: {recommender_name} -- recommendation: {recommendation}\n -- summary:".format(
        **raw_data
    )
    response = get_completion(bullet_model_id="recent_recommendation_2", prompt=prompt)

    return {"raw_data": raw_data, "prompt": prompt, "response": response}
