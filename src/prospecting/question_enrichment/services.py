import datetime
from operator import and_, or_
from model_import import QuestionEnrichmentRequest, QuestionEnrichmentRow
from app import db, celery
from src.company.models import Company
from src.ml.openai_wrappers import wrapped_chat_gpt_completion
from src.prospecting.models import Prospect
from src.prospecting.question_enrichment.models import QuestionEnrichmentRowStatus

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

@celery.task()
def create_question_enrichment_row(
    prospect_id: int,
    question: str,
    retries: int,
    error: str
):
    row = QuestionEnrichmentRow(
        prospect_id=prospect_id,
        question=question,
        status=QuestionEnrichmentRowStatus.QUEUED,
        retries=retries,
        error=error
    )
    db.session.add(row)
    db.session.commit()

    return row

@celery.task(bind=True)
def find_and_run_queued_question_enrichment_row(
    self, num_rows=1
):
    # Current time minus 3 minutes
    three_minutes_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=3)

    row = QuestionEnrichmentRow.query.filter(
        or_(
            QuestionEnrichmentRow.status == "QUEUED",
            or_(
                and_(
                    QuestionEnrichmentRow.status == "ERROR",
                    QuestionEnrichmentRow.retries < 3
                ),
                and_(
                    QuestionEnrichmentRow.status == "IN_PROGRESS",
                    QuestionEnrichmentRow.updated_at < three_minutes_ago
                )
            )
            
        )
    ).limit(num_rows).all()

    if len(row) == 0:
        return None
    
    for r in row:
        run_question_enrichment_row.delay(r.id)

    db.session.commit()

@celery.task(bind=True)
def run_question_enrichment_row(
    self,
    row_id: int
):
    try:
        request: QuestionEnrichmentRow = QuestionEnrichmentRow.query.filter_by(id=row_id).first()
        request.retries = request.retries + 1
        request.status = QuestionEnrichmentRowStatus.IN_PROGRESS
        request.error = None
        db.session.add(request)
        db.session.commit()

        request = QuestionEnrichmentRow.query.filter_by(id=row_id).first()

        if request is None:
            raise Exception("Question enrichment request not found")
        
        prospect_id: int = request.prospect_id
        prospect: Prospect = Prospect.query.filter_by(id=prospect_id).first()
        if prospect is None:
            raise Exception("Prospect not found")
        
        company = None
        if prospect:
            company: Company = Company.query.filter_by(id=prospect.company_id).first()

        completion = wrapped_chat_gpt_completion(
            messages=[
                {
                    'role': 'user',
                    'content': """You are a researcher that is helping me answer a question. Here is information about the prospect:
    Prospect Name: {prospect_name}
    Prospect Title: {prospect_title}
    ------
    Company: {company_name}
    Company Description: {company_description}

    Here is the question you want to answer:
    '''
    {question}
    '''

    Given this information and the question, respond with TRUE or FALSE exactly.

    Output:""".format(
                prospect_name=prospect.full_name if prospect is not None else "Unknown",
                prospect_title=prospect.title if prospect is not None else "Unknown",
                company_name=company.name if company is not None else "Unknown",
                company_description=company.description if company is not None else "Unknown",
                question=request.question
            ),
                }
            ]
        )

        if completion is None:
            raise Exception("Completion is None")
        
        if 'true' in completion.lower():
            request.output = True
        elif 'false' in completion.lower():
            request.output = False
        else:
            raise Exception("Completion is not true or false")
        
        request.status = QuestionEnrichmentRowStatus.COMPLETE
        db.session.add(request)
        db.session.commit()
    except Exception as e:
        request= QuestionEnrichmentRow.query.filter_by(id=row_id).first()

        request.error = str(e)
        request.status = QuestionEnrichmentRowStatus.ERROR
        db.session.add(request)
        db.session.commit()