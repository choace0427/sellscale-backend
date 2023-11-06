import datetime
from operator import and_, or_
from model_import import QuestionEnrichmentRequest, QuestionEnrichmentRow
from app import db, celery
from src.company.models import Company
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.prospecting.models import Prospect

def create_question_enrichment_request(
    prospect_ids: list,
    question: str
):
    request = QuestionEnrichmentRequest(
        prospect_ids=prospect_ids,
        question=question
    )
    db.session.add(request)
    db.session.commit()

    # create question enrichment rows
    for prospect_id in prospect_ids:
        create_question_enrichment_row.delay(
            prospect_id=prospect_id,
            question=question,
            retries=0,
            error=None
        )

    return request

@celery.task(name="question_enrichment.create_question_enrichment_row")
def create_question_enrichment_row(
    prospect_id: int,
    question: str,
    retries: int,
    error: str
):
    row = QuestionEnrichmentRow(
        prospect_id=prospect_id,
        question=question,
        complete=False,
        retries=retries,
        error=error
    )
    db.session.add(row)
    db.session.commit()

    return row

@celery.task(bind=True, name="question_enrichment.find_and_run_queued_question_enrichment_row")
def find_and_run_queued_question_enrichment_row(
    self, num_rows=1
):
    # Current time minus 3 minutes
    three_minutes_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=3)

    row = QuestionEnrichmentRow.query.filter(
        or_(
            # QUEUED items
            QuestionEnrichmentRow.status == "QUEUED",
            and_(
                QuestionEnrichmentRow.status == "FAILED",
                QuestionEnrichmentRow.retries < 3
            ),
            and_(
                QuestionEnrichmentRow.status == "IN_PROGRESS",
                QuestionEnrichmentRow.updated_at < three_minutes_ago
            )
        )
    ).limit(num_rows).all()

    if len(row) == 0:
        return None
    
    for r in row:
        r.status = "IN_PROGRESS"
        db.session.add(r)
        run_question_enrichment_row.delay(r.id)

    db.session.commit()

def run_question_enrichment_row(
    request_id: int
):
    request: QuestionEnrichmentRow = QuestionEnrichmentRow.query.filter_by(id=request_id).first()

    if request is None:
        raise Exception("Question enrichment request not found")
    
    prospect_id: int = request.prospect_id
    prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
    company: Company = Company.query.filter_by(id=prospect.company_id).first()

    for prospect_id in request.prospect_ids:
        completion = wrapped_chat_gpt_completion(
            messages=[
                {
                    'role': 'user',
                    'content': """You are a researcher that is helping me answer a question. Here is information about the prospect:
Prospect Name: {prospect_name}
Prospect Title: {prospect_title}
------
Company: {company_name}
Company Tagline: {company_tagline}
Company Description: {company_description}

Here is the question you want to answer:
'''
{question}
'''

Given this information and the question, respond with TRUE or FALSE exactly.

Output:""".format(
                prospect_name=prospect.name if prospect.name is not None else "Unknown",
                prospect_title=prospect.title if prospect.title is not None else "Unknown",
                company_name=company.name if company is not None else "Unknown",
                company_tagline=company.tagline if company is not None else "Unknown",
                company_description=company.description if company is not None else "Unknown",
                question=request.question
            ),
                }
            ]
        )

    return request