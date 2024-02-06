from datetime import datetime

from src.ml.openai_wrappers import (
    wrapped_create_completion,
    OPENAI_COMPLETION_DAVINCI_3_MODEL,
)

from src.utils.abstract.attr_utils import deep_get


def get_recent_recommendation_summary(prospect_id: int, data: dict):
    # saw _______'s recommendation of you. Seems like _________

    recommender_name = deep_get(data, "personal.recommendations.0.first_name", "")
    recommendation = deep_get(data, "personal.recommendations.0.text", "")
    created_at = deep_get(data, "personal.recommendations.0.created_at")

    if not created_at:
        return {}

    years_since_recommendation = (
        datetime.now() - datetime.fromisoformat(created_at)
    ).days / 365

    raw_data = {
        "recommender_name": recommender_name,
        "recommendation": recommendation,
    }

    few_shot_1 = "recommender name: Devin\nrecommendation: I have worked with Olga for 2 years during which I have always admired her exceptionally professional management style. She is extremely patient, friendly and considerate and delivers high quality results mostly ahead of schedule. Olga is a fantastic person to work with.\nsummary: In a recommendation, Devin mentioned that they are an incredibly professional manager and delivers high quality results on time."
    few_shot_2 = "recommender name: Serene\nrecommendation: Samreen gave me excellent advice with health and sleep.  I sought her advice after having developed bad eating, exercise and sleeping habits.  The biggest thing that she did is help me identify my blind spots, which were causing a decline in my productivity and level of life satisfaction.  Once my blind spots were revealed, she helped me set goals and action steps to meet those goals.  Then, I was able to see progress.  I would highly recommend Samreen to anyone who is searching for an empathetic, skilled and encouraging coach in life habits!\nsummary: From a recommendation, Serene said that they provided empathetic guidance and coaching about life habits."
    few_shot_3 = "recommender name: Miaoer\nrecommendation: Hansen was the product intern on the team I led at realtor.com in 2018.  Despite being his first product role, Hansen had a penchant for grasping things quickly, which combined well with his passion for building great products. At the conclusion of his internship, he has demonstrated several traits of a strong PM: strong user empathy, intellectual curiosity, communication/collaboration and problem solving. I am confident he will be a great asset to a strong product team.\nsummary: Saw in a recommendation, Miaoer wrote that they are a passionate and intellectually curious individual."

    instruction = f'You\'re writing a short sentence summary of a recent recommendation an individual has received. Only include one sentence of their top 3 most impactful attributes. Include the name of the recommender. Begin the summary with the words "In a recommendation". Limit your summary to a maximum of 30 words. Use "they" and "their" to refer to the individual.\n\nexamples:\n\n{few_shot_1}\n\n{few_shot_2}\n\n{few_shot_3}'
    prompt = f"{instruction}\n\n----\n\nrecommender name: {raw_data['recommender_name']}\nrecommendation: {raw_data['recommendation']}\nsummary: "

    if not recommender_name or not recommendation or years_since_recommendation > 5:
        return {}
    else:
        response = wrapped_create_completion(
            model=OPENAI_COMPLETION_DAVINCI_3_MODEL, prompt=prompt, max_tokens=50
        )

    return {"raw_data": raw_data, "prompt": prompt, "response": response}
