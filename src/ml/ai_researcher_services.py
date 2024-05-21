import json
from app import db
from model_import import ClientSDR, AIResearcher, AIResearcherQuestion, AIResearcherAnswer, ClientArchetype, Prospect
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

def create_ai_researcher(
    name: str,
    client_sdr_id: int
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

def get_ai_researcher_answers_for_prospect(
    prospect_id: int
):
    """Get all AI Researcher answers for a prospect."""
    answers: list[AIResearcherAnswer] = AIResearcherAnswer.query.filter_by(prospect_id=prospect_id).all()

    return [answer.to_dict(deep_get=True) for answer in answers]

def run_all_ai_researcher_questions_for_prospect(
    client_sdr_id: int,
    prospect_id: int
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
            question_id=question.id
        )

    return True

def run_ai_researcher_question(
    client_sdr_id: int,
    prospect_id: int,
    question_id: int
):
    """Run an AI Researcher question on a prospect."""
    question: AIResearcherQuestion = AIResearcherQuestion.query.get(question_id)

    import pdb; pdb.set_trace()

    if question.type == "QUESTION":
        success, raw_response, data = answer_question_about_prospect(
            client_sdr_id=client_sdr_id,
            prospect_id=prospect_id,
            question=question.key,
            how_its_relevant=question.relevancy
        )

        if not success:
            is_yes_response = False
            short_summary = "Could not find the information related to this query."
            raw_response = "None."
        else:
            is_yes_response = data["is_yes_response"]
            short_summary = data["cleaned_research"]
            raw_response = raw_response
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
            raw_response = "None."
        else:
            raw_value = research_point.value
            rp_type = research_point.research_point_type

            validate_with_gpt = wrapped_chat_gpt_completion(
                messages=[
                    {
                        'role': 'system',
                        'content': "You are an AI sales researcher that is taking a snippet from a Linkedin profile, a qualifying relevancy criteria, and responding with a short summary and raw response. I need you to respond with a JSON with three items: is_yes_response (bool) a simple true or false if the response is a positive response or not. 'No' responses are false, 'Yes' responses are true, and 'Unknown' responses are false too.\ncleaned_research(str) Simply explain why the response is a yes or no response. This should be a short summary of the response that explains simply"
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
            short_summary = validate_with_gpt["cleaned_research"]
            raw_response = raw_value
    else:
        return False

    ai_researcher_answer: AIResearcherAnswer = AIResearcherAnswer(
        prospect_id=prospect_id,
        question_id=question_id,
        is_yes_response=is_yes_response,
        short_summary=short_summary,
        raw_response=raw_response
    )
    db.session.add(ai_researcher_answer)
    db.session.commit()

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
    relevancy: str
):
    """Edit a question."""
    question: AIResearcherQuestion = AIResearcherQuestion.query.get(question_id)

    question.key = key
    question.relevancy = relevancy

    db.session.add(question)
    db.session.commit()

    return True