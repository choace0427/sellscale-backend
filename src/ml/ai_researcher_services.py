import json
from typing import Optional
from app import db
from model_import import Client, ClientSDR, AIResearcher, AIResearcherQuestion, AIResearcherAnswer, ClientArchetype, Prospect
from src.email_outbound.models import ProspectEmail
from src.message_generation.models import GeneratedMessage
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.ml.services import answer_question_about_prospect
from src.research.models import ResearchPayload, ResearchPoints, ResearchType

def get_ai_researchers_for_client(
    client_sdr_id: int
):
    """Get all AI Researchers for a client."""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    researchers: list[AIResearcher] = AIResearcher.query.filter_by(client_id=client_id).all()

    return [researcher.to_dict() for researcher in researchers]

def create_default_ai_researcher(
    client_sdr_id: int,
):
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False
    client_id = client_sdr.client_id
    if not client_id:
        return False

    all_sdrs: list[ClientSDR] = ClientSDR.query.filter_by(client_id=client_id).all()
    all_ids = [sdr.id for sdr in all_sdrs]
    if not all_ids:
        return False

    all_researchers: list[AIResearcher] = AIResearcher.query.filter(
        AIResearcher.client_sdr_id_created_by.in_(all_ids)
    ).all()
    if len(all_researchers) > 0:
        return False
    
    researcher: AIResearcher = AIResearcher(
        name="Default AI Researcher",
        client_id=client_id,
        client_sdr_id_created_by=client_sdr_id
    )
    db.session.add(researcher)
    db.session.commit()

    return True

def auto_assign_ai_researcher_to_client_archetype(
    client_archetype_id: int
):
    """Auto assigns the most recent AI Researcher to a client archetype."""
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not client_archetype:
        return False
    client_id = client_archetype.client_id
    if not client_id:
        return False

    all_researchers: list[AIResearcher] = AIResearcher.query.filter(
        AIResearcher.client_id == client_id
    ).order_by(AIResearcher.created_at.desc()).all()
    if len(all_researchers) == 0:
        return False

    ai_researcher_id = all_researchers[0].id

    client_archetype.ai_researcher_id = ai_researcher_id
    db.session.add(client_archetype)
    db.session.commit()

    return True

def create_ai_researcher(
    name: str,
    client_sdr_id: int,
    archetype_id: Optional[int] = None
):
    """Create an AI Researcher for a client."""
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client_id = client_sdr.client_id

    researcher: AIResearcher = AIResearcher(
        name=name,
        client_id=client_id,
        client_sdr_id_created_by=client_sdr_id
    )
    db.session.add(researcher)
    db.session.commit()

    if archetype_id:
        client_archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
        client_archetype.ai_researcher_id = researcher.id
        db.session.add(client_archetype)
        db.session.commit()

    return True

def get_ai_researcher_questions_for_researcher(
    researcher_id: int
):
    """Get all questions for an AI Researcher."""
    questions: list[AIResearcherQuestion] = AIResearcherQuestion.query.filter_by(researcher_id=researcher_id).all()

    return [question.to_dict() for question in questions]

def create_ai_researcher_question(
    type: str,
    key: str,
    relevancy: str,
    researcher_id: int
):
    """Create a question for an AI Researcher."""
    ai_researcher_question: AIResearcherQuestion = AIResearcherQuestion(
        type=type,
        key=key,
        relevancy=relevancy,
        researcher_id=researcher_id
    )
    db.session.add(ai_researcher_question)
    db.session.commit()

    return True

def generate_ai_researcher_questions(
    researcher_id: int, client_sdr_id: int, campaign_id: int
):
    
    from src.ml.services import get_text_generation
    from src.client.services_client_archetype import get_client_archetype_sequences

    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    archetype: ClientArchetype = ClientArchetype.query.get(campaign_id)

    sequences = get_client_archetype_sequences(campaign_id)
    email_sequence = sequences.get("email_sequence", [])
    linkedin_sequence = sequences.get("linkedin_sequence", [])

    # Determine the longest sequence
    if email_sequence or linkedin_sequence:
        longest_sequence = max(email_sequence, linkedin_sequence, key=len)
        # Find the archetype_example_sequence based on the longest sequence
        archetype_example_sequence = max(
            (step["description"] for step in longest_sequence),
            key=len,
            default=""
        )
    else:
        longest_sequence = []
        archetype_example_sequence = "N/A."

    # Print active sequences
    print("Email Sequence:", email_sequence)
    print("LinkedIn Sequence:", linkedin_sequence)

    prompt = f'''We are reaching out to {archetype.archetype}. We are {client.company}, 
    {client.description}. Angle: The questions we ask 
    will be specific to this campaign. Here's the first email template to infer what this campaign is about
    to generate research questions for: 
    
    {archetype_example_sequence} 
    
    Come up with some research questions I can use to use in my outbound campaign. GOOD RESEARCH: Questions I 
    can find or search on google, reddit, youtube videos, articles, etc. eg. "Is the company hiring for
    data engineers Relevance: this is relevant if they are hiring for data engineers, because it could 
    suggest the CTO is overwhelmed and we can mention this in outreach. BAD RESEARCH: Questions that 
    are hard to find publicly, super specific, or not relevant Please come up with 3-4 questions for 
    research. Format: Question: [question here] Relevance: [Yes/no]. [Relevance reason]
          
    If you are asking about their company
    specifically please use a placeholder like so, e.g. "what is [[company]]'s ... ?" The data should be in JSON format with the following structure:

        [
            {{
                "Question": "[question here]",
                "Relevant": "[Yes/No]",
                "RelevanceReason": "[Relevance reason]"
            }},
            ...
        ]

        Only respond with the JSON, nothing else.
        '''
    
    def get_response_with_retries(prompt, retries=3):
        for attempt in range(retries):
            response = get_text_generation(
                [{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=600,
                model='gpt-4o',
                type="MISC_CLASSIFY",
            )
            print('Attempt', attempt + 1, 'response:', response)
            try:
                response_json = json.loads(response)
                return response_json
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON on attempt {attempt + 1}: {e}")
        return None

    response_json = get_response_with_retries(prompt)

    questions_and_relevancy = []
    if response_json:
        for item in response_json:
            question = item.get("Question", "").strip()
            relevancy_info = item.get("Relevant", "").strip()
            relevance_reason = item.get("RelevanceReason", "").strip()
            questions_and_relevancy.append({
                "question": question,
                "relevancy": relevancy_info,
                "relevance_reason": relevance_reason
            })
    else:
        print("Failed to decode JSON after multiple attempts.")
    print(response_json)

    return response_json



    

def get_ai_researcher_answers_for_prospect(
    prospect_id: int
):
    """Get all AI Researcher answers for a prospect."""
    answers: list[AIResearcherAnswer] = AIResearcherAnswer.query.filter_by(prospect_id=prospect_id).all()

    return [answer.to_dict(deep_get=True) for answer in answers]

def run_all_ai_researcher_questions_for_prospect(
    client_sdr_id: int,
    prospect_id: int,
    room_id: Optional[str] = None
):
    prospect: Prospect = Prospect.query.get(prospect_id)
    client_archetype_id = prospect.archetype_id
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    ai_researcher_id = client_archetype.ai_researcher_id

    questions: list[AIResearcherQuestion] = AIResearcherQuestion.query.filter_by(researcher_id=ai_researcher_id).all()

    # Delete all existing answers for this prospect
    existing_answers: list[AIResearcherAnswer] = AIResearcherAnswer.query.filter_by(prospect_id=prospect_id).all()
    for answer in existing_answers:
        db.session.delete(answer)
    db.session.commit()

    for question in questions:
        # todo(Aakash) - in future, make this a celery task if it's too slow.
        run_ai_researcher_question(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            question_id=question.id,
            room_id=room_id
        )

    from src.sockets.services import send_socket_message
    if (room_id):
        send_socket_message('stream-answers', {"message":"done"}, room_id)

    return True

def run_ai_researcher_question(
    client_sdr_id: int,
    prospect_id: int,
    question_id: int,
    room_id: str
):
    """Run an AI Researcher question on a prospect."""
    question: AIResearcherQuestion = AIResearcherQuestion.query.get(question_id)

    if question.type == "QUESTION":
        print("Running question type question", "with data", question.key, question.relevancy, "for prospect", prospect_id)
        success, raw_response, data = answer_question_about_prospect(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            question=question.key,
            how_its_relevant=question.relevancy,
            room_id=room_id,
            questionType=question.type
        )

        if not success:
            is_yes_response = False
            short_summary = "Could not find the information related to this query."
            relevancy_explanation = "Could not find the information related to this query."
            raw_response = "None."
        else:
            is_yes_response = data["is_yes_response"]
            short_summary = data["cleaned_research"]
            relevancy_explanation = data["relevancy_explanation"]
            raw_response = raw_response

        ai_researcher_answer: AIResearcherAnswer = AIResearcherAnswer(
            prospect_id=prospect_id,
            question_id=question_id,
            is_yes_response=is_yes_response,
            short_summary=short_summary,
            raw_response=raw_response,
            relevancy_explanation=relevancy_explanation
        )
        db.session.add(ai_researcher_answer)
        db.session.commit()
    elif question.type == "LINKEDIN":
        research_payloads: list[ResearchPayload] = ResearchPayload.query.filter_by(
            prospect_id=prospect_id
        ).filter(
            ResearchPayload.research_type == ResearchType.LINKEDIN_ISCRAPER
        ).order_by(ResearchPayload.created_at.desc()).all()

        research_point: ResearchPoints = ResearchPoints.query.filter(
            ResearchPoints.research_payload_id.in_([rp.id for rp in research_payloads])
        ).filter(
            ResearchPoints.research_point_type == question.key
        ).first()

        if not research_point:
            is_yes_response = False
            short_summary = "Could not find the information related to this query."
            relevancy_explanation = "Could not find the information related to this query."
            raw_response = "None."
        else:
            raw_value = research_point.value
            rp_type = research_point.research_point_type

            validate_with_gpt = wrapped_chat_gpt_completion(
                messages=[
                    {
                        'role': 'system',
                        'content': "You are an AI sales researcher that is taking a snippet from a Linkedin profile, a qualifying relevancy criteria, and responding with a short summary and raw response. I need you to respond with a JSON with three items: is_yes_response (bool) a simple true or false if the response is a relevant response or not. 'Irrelevant' responses are false, 'Relevant' responses are true, and 'Unknown' responses are false too.\ncleaned_research(str) Simply explain why the response is a yes or no response. This should be a short summary of the response that explains simply\nrelevancy_explanation (str): A simple sentence that should indicate if the research is relevant or nor irrelevant, with a short 1 sentence justification why."
                    },
                    {
                    'role': 'user',
                    'content': f"Research point type: {rp_type}\nResearch point value: {raw_value}\nRelevancy: {question.relevancy}\nOutput:"
                    }
                ],
                max_tokens=100,
                model='gpt-4o'
            )
            validate_with_gpt = json.loads(
                validate_with_gpt.replace("json", "").replace("`", "")
            )

            is_yes_response = validate_with_gpt["is_yes_response"]
            short_summary = raw_value
            relevancy_explanation = validate_with_gpt["relevancy_explanation"]
            raw_response = validate_with_gpt["cleaned_research"]

        ai_researcher_answer: AIResearcherAnswer = AIResearcherAnswer(
            prospect_id=prospect_id,
            question_id=question_id,
            is_yes_response=is_yes_response,
            short_summary=short_summary,
            raw_response=raw_response,
            relevancy_explanation=relevancy_explanation
        )
        db.session.add(ai_researcher_answer)
        db.session.commit()
    elif question.type == "GENERAL":
        # Step 1: Ask perplexity for general information
        # Step 2: extract key points from the response using GPT-4o
        # step 3: for each key point, generate a short summary and relevancy explanation and save it as an answer

        success, raw_response, data = answer_question_about_prospect(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            question=question.key,
            how_its_relevant=question.relevancy,
            room_id=room_id,
            questionType=question.type
        )

        if not success:
            is_yes_response = False
            short_summary = "Could not find the information related to this query."
            relevancy_explanation = "Could not find the information related to this query."
            raw_response = "None."

            ai_researcher_answer: AIResearcherAnswer = AIResearcherAnswer(
                prospect_id=prospect_id,
                question_id=question_id,
                is_yes_response=is_yes_response,
                short_summary=short_summary,
                raw_response=raw_response,
                relevancy_explanation=relevancy_explanation
            )
            db.session.add(ai_researcher_answer)
            db.session.commit()
        
        # step 2
        key_points = wrapped_chat_gpt_completion(
            messages=[
                {
                    'role': 'system',
                    'content': "You are an AI data extractor that, given some raw research information and relevancy explanation, will extract the relevant and key information from the research. I need you to respond with a JSON object. Make a list called `data` which contains a list of objects representing the relevant extracted information with the following two items: key_point_summary (str) a single key points extracted from the research (grab the contents verbatim), and relevancy_explanation (str): A simple sentence that should indicate if the research is relevant or nor irrelevant, with a short 1 sentence justification why.\n\nIMPORTANT: Only respond with the JSON, nothing else.\n\nIMPORTANT: Extract 2-4 key points from the research and provide a relevancy explanations for each key point."
                },
                {
                    'role': 'user',
                    'content': f"Raw Research Data: {raw_response}\nRelevancy Explanation: {question.relevancy}\nOutput:"
                }
            ],
            max_tokens=1000,
            model='gpt-4o'
        )

        data = json.loads(
            key_points.replace("json", "").replace("`", "")
        )


        for key_point in data["data"]:
            ai_researcher_answer: AIResearcherAnswer = AIResearcherAnswer(
                prospect_id=prospect_id,
                question_id=question_id,
                is_yes_response=True,
                short_summary=key_point["key_point_summary"],
                raw_response=raw_response,
                relevancy_explanation=key_point["relevancy_explanation"]
            )
            db.session.add(ai_researcher_answer)
            db.session.commit()
    else:
        return False

    

    return True

def connect_researcher_to_client_archetype(
    client_sdr_id: int,
    client_archetype_id: int,
    ai_researcher_id: int
):
    """Connect an AI Researcher to a client archetype."""
    client_archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    ai_researcher: AIResearcher = AIResearcher.query.get(ai_researcher_id)

    if client_archetype.client_sdr_id != client_sdr_id:
        return False
    if ai_researcher.client_id != client_archetype.client_id:
        return False
    
    client_archetype.ai_researcher_id = ai_researcher_id
    db.session.add(client_archetype)
    db.session.commit()

    return True

def delete_question(
    question_id: int
):
    """Delete a question."""
    # delete all answers for this question
    answers: list[AIResearcherAnswer] = AIResearcherAnswer.query.filter_by(question_id=question_id).all()
    for answer in answers:
        db.session.delete(answer)
    db.session.commit()

    question: AIResearcherQuestion = AIResearcherQuestion.query.get(question_id)
    db.session.delete(question)
    db.session.commit()

    return True

def edit_question(
    question_id: int,
    key: str,
    relevancy: str,
    question_type: str
):
    """Edit a question."""
    question: AIResearcherQuestion = AIResearcherQuestion.query.get(question_id)

    question.key = key
    question.type = question_type
    question.relevancy = relevancy

    db.session.add(question)
    db.session.commit()

    return True

def get_generated_email(email_body, prospectId):
    try:
        prospect: Prospect = Prospect.query.get(prospectId)
        if not prospect:
            return False

        name = prospect.first_name
        title = prospect.title
        company = prospect.company

        research_list = get_ai_researcher_answers_for_prospect(prospectId)
        if not research_list:
            return False

        research = ', '.join([str(answer) for answer in research_list])

        prompt = f"""
        You are an emailer personalizer. Combine the sequence provided with the personalization to create a personalized email. Keep it as short as possible. Feel free to spread the personalizations across the email to keep length minimal. Try to include personalization at the beginning since it helps with open rates.

        Original Email: {email_body} ### Personalization: {research}

        Prospect Information:
        - name: {name}
        - title: {title} @ {company}

        Tie in relevant details into the emails so it is compelling for the person I am reaching out to.

        Example
        Hi Dr Xyz..

        Tie in relevant details into the emails so it is compelling for the person I am reaching out to.
        NOTE: Try not to increase the length of the email - seamlessly incorporate personalization to make it same or shorter length.
        NOTE: Include the personalization at the beginning since that makes for a better hook and helps open rates.
        NOTE: Only respond with the personalized email, nothing else.

        Personalized email:
        """

        answer = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model='claude-3-opus-20240229',
            max_tokens=1000
        )

        return answer
    except Exception as e:
        print(e)
        return False

def run_ai_personalizer_on_prospect_email(prospect_email_id: int):
    try:
        prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
        prospect_id: int = prospect_email.prospect_id
        prospect: Prospect = Prospect.query.get(prospect_id)

        run_all_ai_researcher_questions_for_prospect(
            client_sdr_id=prospect.client_sdr_id,
            prospect_id=prospect_id
        )

        email_body_id = prospect_email.personalized_body
        generated_message: GeneratedMessage = GeneratedMessage.query.get(email_body_id)
        origina_email_body = generated_message.completion

        positive_research_points = AIResearcherAnswer.query.filter_by(prospect_id=prospect_id, is_yes_response=True).all()

        if len(positive_research_points) == 0:
            return False

        personalizations = ""
        for point in positive_research_points:
            point: AIResearcherAnswer = point
            question: AIResearcherQuestion = AIResearcherQuestion.query.get(point.question_id)

            raw_data = point.raw_response
            relevancy_reason = question.relevancy
            relevancy_explanation = point.relevancy_explanation

            personalizations += f"Raw Data: {raw_data}\nQuestion: {relevancy_reason}\nRelevancy Explanation: {relevancy_explanation}\n\n"

        prompt = """
    You are an emailer personalizer. Combine the sequence provided with the personalization to create a personalized email. Keep it as short as possible. Feel free to spread the personalizations across the email to keep length minimal. Try to include personalization at the beginning since it helps with open rates.

    Original Email:
    {original_email_body}

    ### Personalization
    {personalizations}

    Prospect Information:
    - name: {name}
    - title: {title}
    - company: {company}

    Tie in relevant details into the emails so it is compelling for the person I am reaching out to.

    Example
    Hi Dr Xyz..

    Tie in relevant details into the emails so it is compelling for the person I am reaching out to.
    NOTE: Try not to increase the length of the email - seamlessly incorproate personalization to make it same or shorter length.
    NOTE: Only respond with the personalized email, nothing else.
    NOTE: When adding personalization throughout the email, ensure that you write in a natural way that is not robotic or forced. Additionally, ensure you tie in the personalization in a way that is relevant to the email content.
    NOTE: I want you to add at least one personalization right after the initial "Hi _____" (or greeting). Do not have anything else before this personalization. It needs to be a personalized and relevant first sentence to the email.

    Personalized email:"""

        prompt = prompt.format(
            original_email_body=origina_email_body,
            personalizations=personalizations,
            name=prospect.first_name,
            title=prospect.colloquialized_title if prospect.colloquialized_title else prospect.title,
            company=prospect.colloquialized_company if prospect.colloquialized_company else prospect.company
        )

        answer = wrapped_chat_gpt_completion(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model='claude-3-opus-20240229',
            max_tokens=1000
        )

        generated_message.completion = answer
        db.session.add(generated_message)
        db.session.commit()

        return True
    except Exception as e:
        print(e)
        return False

def simulate_voice_message(text, voice_params):
    # Filter out parameters with a value of 50
    filtered_params = {
        "Warmth": voice_params['warmth_confidence']['x'],
        "Confidence": voice_params['warmth_confidence']['y'],
        "Humor": voice_params['humor_seriousness']['x'],
        "Seriousness": voice_params['humor_seriousness']['y'],
        "Assertiveness": voice_params['assertiveness_empathy']['x'],
        "Empathy": voice_params['assertiveness_empathy']['y'],
        "Optimism": voice_params['optimism_professionalism']['x'],
        "Professionalism": voice_params['optimism_professionalism']['y']
    }

    # Create the prompt string with only the relevant parameters
    prompt = "You are a message emotion adjuster. Adjust the text to reflect the following emotional parameters:\n"
    adjustments_found = False
    for param, value in filtered_params.items():
        if not (47 < int(float(value)) < 53):
            adjustments_found = True
            prompt += f"- {param}: {value}%\n"
            if param == "Warmth":
                prompt += "  (0-10%: Extremely cold, 10-20%: Very cold, 20-30%: Cold, 30-40%: Slightly cold, 40-50%: Neutral, 50-60%: Slightly warm, 60-70%: Warm, 70-80%: Very warm, 80-90%: Extremely warm, 90-100%: Overly warm)\n"
            elif param == "Confidence":
                prompt += "  (0-10%: Extremely unconfident, 10-20%: Very unconfident, 20-30%: Unconfident, 30-40%: Slightly unconfident, 40-50%: Neutral, 50-60%: Slightly confident, 60-70%: Confident, 70-80%: Very confident, 80-90%: Extremely confident, 90-100%: Overly confident)\n"
            elif param == "Humor":
                prompt += "  (0-10%: Extremely serious, 10-20%: Very serious, 20-30%: Serious, 30-40%: Slightly serious, 40-50%: Neutral, 50-60%: Slightly humorous, 60-70%: Humorous, 70-80%: Very humorous, 80-90%: Extremely humorous, 90-100%: Overly humorous)\n"
            elif param == "Seriousness":
                prompt += "  (0-10%: Extremely humorous, 10-20%: Very humorous, 20-30%: Humorous, 30-40%: Slightly humorous, 40-50%: Neutral, 50-60%: Slightly serious, 60-70%: Serious, 70-80%: Very serious, 80-90%: Extremely serious, 90-100%: Overly serious)\n"
            elif param == "Assertiveness":
                prompt += "  (0-10%: Extremely passive, 10-20%: Very passive, 20-30%: Passive, 30-40%: Slightly passive, 40-50%: Neutral, 50-60%: Slightly assertive, 60-70%: Assertive, 70-80%: Very assertive, 80-90%: Extremely assertive, 90-100%: Overly assertive)\n"
            elif param == "Empathy":
                prompt += "  (0-10%: Extremely unempathetic, 10-20%: Very unempathetic, 20-30%: Unempathetic, 30-40%: Slightly unempathetic, 40-50%: Neutral, 50-60%: Slightly empathetic, 60-70%: Empathetic, 70-80%: Very empathetic, 80-90%: Extremely empathetic, 90-100%: Overly empathetic)\n"
            elif param == "Optimism":
                prompt += "  (0-10%: Extremely pessimistic, 10-20%: Very pessimistic, 20-30%: Pessimistic, 30-40%: Slightly pessimistic, 40-50%: Neutral, 50-60%: Slightly optimistic, 60-70%: Optimistic, 70-80%: Very optimistic, 80-90%: Extremely optimistic, 90-100%: Overly optimistic)\n"
            elif param == "Professionalism":
                prompt += "  (0-10%: Extremely unprofessional, 10-20%: Very unprofessional, 20-30%: Unprofessional, 30-40%: Slightly unprofessional, 40-50%: Neutral, 50-60%: Slightly professional, 60-70%: Professional, 70-80%: Very professional, 80-90%: Extremely professional, 90-100%: Overly professional)\n"

    if not adjustments_found:
        return text
    prompt += """
    Please make sure that all of these parameters are reflected in the text in some way, but make it natural.

    Original Text: {text}

    Adjusted Text:

    Only respond with the adjusted text, nothing else. Make it sound human and change the text enough to reflect the emotional parameters.
    """.format(text=text)
    print('prompt:', prompt)

    adjusted_text = wrapped_chat_gpt_completion(
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        model='gpt-4o',
        max_tokens=500
    )

    return adjusted_text
