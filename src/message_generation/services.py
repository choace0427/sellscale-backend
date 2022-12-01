from src.ml.adverserial_ai import get_adversarial_ai_approval
from src.ml.models import GNLPModelType
from model_import import (
    GeneratedMessageType,
    GeneratedMessage,
    EmailSchema,
    GeneratedMessageStatus,
    ProspectEmail,
    ProspectStatus,
    GeneratedMessageFeedback,
    GeneratedMessageJob,
    GeneratedMessageJobStatus,
)
from src.email_outbound.models import ProspectEmailStatus
from src.research.models import ResearchPayload, ResearchPoints
from src.utils.random_string import generate_random_alphanumeric
from model_import import Prospect
from ..ml.fine_tuned_models import (
    get_basic_openai_completion,
    get_completion,
    get_custom_completion_for_client,
)
from src.email_outbound.services import create_prospect_email
from ..utils.abstract.attr_utils import deep_get
import random
from app import db, celery
from tqdm import tqdm
import openai
from flair.data import Sentence
from flair.models import SequenceTagger

tagger = SequenceTagger.load("ner")

import datetime


@celery.task
def research_and_generate_outreaches_for_prospect_list(
    prospect_ids: list, cta_id: int = None
):
    batch_id = generate_random_alphanumeric(36)
    for prospect_id in tqdm(prospect_ids):
        does_job_exist = GeneratedMessageJob.query.filter(
            GeneratedMessageJob.prospect_id == prospect_id,
            GeneratedMessageJob.status == GeneratedMessageJobStatus.PENDING,
        ).first()
        if does_job_exist:
            continue

        gm_job: GeneratedMessageJob = create_generated_message_job(
            prospect_id=prospect_id, batch_id=batch_id
        )
        gm_job_id: int = gm_job.id

        research_and_generate_outreaches_for_prospect.delay(
            prospect_id=prospect_id,
            cta_id=cta_id,
            batch_id=batch_id,
            gm_job_id=gm_job_id,
        )

    return True


@celery.task
def generate_outreaches_for_prospect_list_from_multiple_ctas(
    prospect_ids: list, cta_ids: list
):
    batch_id = generate_random_alphanumeric(36)
    for i, prospect_id in enumerate(tqdm(prospect_ids)):
        cta_id = cta_ids[i % len(cta_ids)]

        does_job_exist = GeneratedMessageJob.query.filter(
            GeneratedMessageJob.prospect_id == prospect_id,
            GeneratedMessageJob.status == GeneratedMessageJobStatus.PENDING,
        ).first()
        if does_job_exist:
            continue

        gm_job: GeneratedMessageJob = create_generated_message_job(
            prospect_id=prospect_id, batch_id=batch_id
        )
        gm_job_id: int = gm_job.id

        research_and_generate_outreaches_for_prospect.delay(
            prospect_id=prospect_id,
            cta_id=cta_id,
            batch_id=batch_id,
            gm_job_id=gm_job_id,
        )


def create_generated_message_job(prospect_id: int, batch_id: str):
    job = GeneratedMessageJob(
        prospect_id=prospect_id,
        batch_id=batch_id,
        status=GeneratedMessageJobStatus.PENDING,
    )
    db.session.add(job)
    db.session.commit()

    return job


def update_generated_message_job_status(gm_job_id: int, status: str):
    gm_job: GeneratedMessageJob = GeneratedMessageJob.query.get(gm_job_id)
    if gm_job:
        gm_job.status = status
        db.session.add(gm_job)
        db.session.commit()


@celery.task(bind=True, max_retries=3)
def research_and_generate_outreaches_for_prospect(
    self, prospect_id: int, batch_id: str, cta_id: str = None, gm_job_id: int = None
):
    try:
        from src.research.linkedin.services import get_research_and_bullet_points_new

        update_generated_message_job_status(
            gm_job_id, GeneratedMessageJobStatus.IN_PROGRESS
        )

        try:
            get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)
            generate_outreaches_for_batch_of_prospects(
                prospect_list=[prospect_id], cta_id=cta_id, batch_id=batch_id
            )
        except:
            update_generated_message_job_status(
                gm_job_id, GeneratedMessageJobStatus.FAILED
            )
            return

        update_generated_message_job_status(
            gm_job_id, GeneratedMessageJobStatus.COMPLETED
        )
    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task
def research_and_generate_emails_for_prospect(prospect_id: int, email_schema_id: int):
    from src.research.linkedin.services import get_research_and_bullet_points_new

    get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)
    generate_prospect_email(prospect_id=prospect_id, email_schema_id=email_schema_id)


def generate_prompt(prospect_id: int, notes: str = ""):
    from model_import import Prospect

    p: Prospect = Prospect.query.get(prospect_id)
    bio_data = {
        "full_name": p.full_name,
        "industry": p.industry,
        "company": p.company,
        "title": p.title,
        "notes": notes,
        "cleaned_bio": p.linkedin_bio,
    }
    prompt = "name: {full_name}<>industry: {industry}<>company: {company}<>title: {title}<>notes: {notes}<>response:".format(
        **bio_data
    )
    prompt = (
        prompt.replace('"', "").replace("\n", "\\n").replace("\r", "").replace("\\", "")
    )

    return prompt


def generate_prompt_permutations_from_notes(notes: dict, n: int = 1):
    perms = []
    notes = [notes[key] for key in notes.keys()]

    for i in range(n):
        sample = ["- " + x for x in random.sample(notes, 2)]
        perms.append(" ".join(sample))

    return perms


def generate_batches_of_research_points(
    points: list, n: int = 1, num_per_perm: int = 2
):
    perms = []
    for i in range(n):
        sample = [x for x in random.sample(points, min(len(points), num_per_perm))]
        perms.append(sample)
    return perms


def generate_outreaches(research_and_bullets: dict, num_options: int = 1):
    profile = research_and_bullets["raw_data"]
    notes = research_and_bullets["bullets"]

    perms = generate_prompt_permutations_from_notes(notes=notes, n=num_options)

    outreaches = []
    for perm in perms:
        prompt = generate_prompt(linkedin_payload=profile, notes=perm)
        completions = get_completion(
            bullet_model_id="baseline_generation", prompt=prompt, max_tokens=90, n=2
        )

        for completion in completions:
            outreaches.append(completion)

    return outreaches


def get_notes_and_points_from_perm(perm, cta_id: int = None):
    from model_import import (
        GeneratedMessageCTA,
    )

    d = ["-" + x.value for x in perm]
    cta = None
    if cta_id:
        cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)

    if cta:
        d.append("-" + cta.text_value)
    notes = "\n".join(d)

    research_points = [x.id for x in perm]

    return notes, research_points, cta


def generate_outreaches_new(prospect_id: int, batch_id: str, cta_id: str = None):
    from model_import import (
        GeneratedMessage,
        GeneratedMessageStatus,
        Prospect,
        GeneratedMessageCTA,
    )

    p: Prospect = Prospect.query.get(prospect_id)
    archetype_id = p.archetype_id

    # check if messages exist, if do don't do anything extra
    messages: list = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id
    ).all()
    if len(messages) > 1:
        return None

    research: ResearchPayload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).first()
    if not research:
        return []

    research_points_list: list[ResearchPoints] = ResearchPoints.query.filter(
        ResearchPoints.research_payload_id == research.id
    ).all()

    perms = generate_batches_of_research_points(points=research_points_list, n=4)

    outreaches = []
    for perm in perms:
        notes, research_points, cta = get_notes_and_points_from_perm(perm, cta_id)

        prompt = generate_prompt(prospect_id=prospect_id, notes=notes)

        completions, model_id = get_custom_completion_for_client(
            archetype_id=archetype_id,
            model_type=GNLPModelType.OUTREACH,
            prompt=prompt,
            max_tokens=90,
            n=2,
        )

        for completion in completions:
            outreaches.append(completion)

            prediction = get_adversarial_ai_approval(prompt=completion)

            message: GeneratedMessage = GeneratedMessage(
                prospect_id=prospect_id,
                gnlp_model_id=model_id,
                research_points=research_points,
                prompt=prompt,
                completion=completion,
                message_status=GeneratedMessageStatus.DRAFT,
                batch_id=batch_id,
                adversarial_ai_prediction=prediction,
                message_cta=cta.id if cta else None,
                message_type=GeneratedMessageType.LINKEDIN,
            )
            db.session.add(message)
            db.session.commit()

    return outreaches


def generate_outreaches_for_batch_of_prospects(
    prospect_list: list, batch_id: str, cta_id: str = None
):
    for prospect_id in tqdm(prospect_list):
        try:
            generate_outreaches_new(
                prospect_id=prospect_id, cta_id=cta_id, batch_id=batch_id
            )
        except Exception as e:
            print(e)
            pass

    return True


def update_message(message_id: int, update: str):
    from model_import import GeneratedMessage

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.completion = update
    message.human_edited = True
    db.session.add(message)
    db.session.commit()

    return True


def approve_message(message_id: int):
    from model_import import GeneratedMessage, GeneratedMessageStatus, Prospect

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    prospect_id = message.prospect_id
    other_approved_messages = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id,
        GeneratedMessage.message_status == GeneratedMessageStatus.APPROVED,
        GeneratedMessage.id != message_id,
    ).all()
    for message in other_approved_messages:
        message.message_status = GeneratedMessageStatus.DRAFT
        db.session.add(message)
        db.session.commit()

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.message_status = GeneratedMessageStatus.APPROVED
    db.session.add(message)

    prospect_id = message.prospect_id
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_outreach_message_id = message.id
    db.session.add(prospect)

    db.session.commit()

    return True


def disapprove_message(message_id: int):
    from model_import import GeneratedMessage, GeneratedMessageStatus

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    prospect_id = message.prospect_id
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_outreach_message_id = None
    message.message_status = GeneratedMessageStatus.DRAFT
    db.session.add(message)
    db.session.add(prospect)
    db.session.commit()

    return True


def pick_new_approved_message_for_prospect(prospect_id: int, message_id: int):
    data = db.session.execute(
        """
            select length(completion), *
            from generated_message
            where prospect_id = {prospect_id}
            order by abs(270 - length(completion)) asc
        """.format(
            prospect_id=prospect_id
        )
    ).fetchall()
    ids = [x["id"] for x in data]
    new_index = (ids.index(message_id) + 1) % len(ids)
    new_message_id = ids[new_index]
    approve_message(message_id=new_message_id)

    return True


def delete_message(message_id: int):
    from model_import import GeneratedMessage, GeneratedMessageStatus, Prospect

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    prospect: Prospect = Prospect.query.get(message.prospect_id)
    prospect.approved_outreach_message_id = None
    db.session.add(prospect)
    db.session.commit()

    db.session.delete(message)
    db.session.commit()

    return True


def delete_message_generation_by_prospect_id(prospect_id: int):
    from model_import import GeneratedMessage

    messages: list = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id
    ).all()

    for message in messages:
        db.session.delete(message)
        db.session.commit()

    return True


def generate_few_shot_generation_prompt(generated_message_ids: list, prospect_id: int):
    from model_import import GeneratedMessage, GeneratedMessageStatus, Prospect

    messages: list = GeneratedMessage.query.filter(
        GeneratedMessage.id.in_(generated_message_ids)
    ).all()

    full_prompt = ""
    for m in messages:
        gm: GeneratedMessage = m
        prospect: Prospect = Prospect.query.get(gm.prospect_id)
        full_name = prospect.full_name
        research_point_ids: list = gm.research_points
        research_points: list = random.sample(
            ResearchPoints.query.filter(
                ResearchPoints.id.in_(research_point_ids)
            ).all(),
            2,
        )

        prompt = (
            """name: {name}\nresearch: {research}\nmessage: {message}\n--\n""".format(
                name=full_name,
                research=". ".join([x.value.strip() for x in research_points]),
                message=gm.completion,
            )
        )
        full_prompt += prompt

    prospect: Prospect = Prospect.query.get(prospect_id)
    research_payload: ResearchPayload = ResearchPayload.query.filter(
        ResearchPayload.prospect_id == prospect_id
    ).first()
    new_research_points_all: list = ResearchPoints.query.filter(
        ResearchPoints.research_payload_id == research_payload.id
    ).all()
    new_research_points = random.sample(
        new_research_points_all, min(len(new_research_points_all), 3)
    )

    new_name = prospect.full_name
    new_research = ". ".join([x.value.strip() for x in new_research_points])

    full_prompt += """name: {new_name}\nresearch: {new_research}\nmessage:""".format(
        new_name=new_name, new_research=new_research
    )

    return full_prompt, [x.id for x in new_research_points]


def few_shot_generations(prospect_id: int, example_ids: list, cta_prompt: str = None):
    from src.research.linkedin.services import get_research_and_bullet_points_new
    from model_import import GeneratedMessage, GeneratedMessageStatus, Prospect

    gm: GeneratedMessage = GeneratedMessage.query.filter(
        GeneratedMessage.prospect_id == prospect_id
    ).first()
    if gm:
        return

    get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

    prompt, research_points = generate_few_shot_generation_prompt(
        generated_message_ids=example_ids, prospect_id=prospect_id
    )

    completions = get_basic_openai_completion(prompt=prompt, max_tokens=60, n=4)

    for completion in completions:
        gm: GeneratedMessage = GeneratedMessage(
            prospect_id=prospect_id,
            gnlp_model_id=5,
            research_points=research_points,
            prompt=prompt,
            completion=completion,
            message_status=GeneratedMessageStatus.DRAFT,
            message_type=GeneratedMessageType.LINKEDIN,
        )
        db.session.add(gm)
        db.session.commit()

    return True


def create_cta(archetype_id: int, text_value: str):
    from model_import import GeneratedMessageCTA

    duplicate_cta_exists = GeneratedMessageCTA.query.filter(
        GeneratedMessageCTA.archetype_id == archetype_id,
        GeneratedMessageCTA.text_value == text_value,
    ).first()
    if duplicate_cta_exists:
        return duplicate_cta_exists

    cta: GeneratedMessageCTA = GeneratedMessageCTA(
        archetype_id=archetype_id, text_value=text_value, active=True
    )
    db.session.add(cta)
    db.session.commit()

    return cta


def delete_cta(cta_id: int):
    from model_import import GeneratedMessageCTA

    generated_message_with_cta = GeneratedMessage.query.filter(
        GeneratedMessage.message_cta == cta_id
    ).first()
    if generated_message_with_cta:
        return False

    cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)
    db.session.delete(cta)
    db.session.commit()

    return True


def toggle_cta_active(cta_id: int):
    from model_import import GeneratedMessageCTA

    cta: GeneratedMessageCTA = GeneratedMessageCTA.query.get(cta_id)
    cta.active = not cta.active
    db.session.add(cta)
    db.session.commit()

    return True


def get_personalized_first_line(
    archetype_id: int,
    model_type: GNLPModelType,
    prompt: str,
    research_points: list,
    prospect_id: int,
    batch_id: int,
):
    completion, model_id = get_custom_completion_for_client(
        archetype_id=archetype_id,
        model_type=GNLPModelType.EMAIL_FIRST_LINE,
        prompt=prompt,
        max_tokens=100,
        n=1,
    )
    personalized_first_line = GeneratedMessage(
        prospect_id=prospect_id,
        gnlp_model_id=model_id,
        research_points=research_points,
        prompt=prompt,
        completion=completion,
        message_status=GeneratedMessageStatus.DRAFT,
        message_type=GeneratedMessageType.EMAIL,
        batch_id=batch_id,
    )
    db.session.add(personalized_first_line)
    db.session.commit()

    return personalized_first_line


def batch_generate_prospect_emails(prospect_ids: list, email_schema_id: int):
    batch_id = generate_random_alphanumeric(32)
    for prospect_id in prospect_ids:
        does_job_exist = GeneratedMessageJob.query.filter(
            GeneratedMessageJob.prospect_id == prospect_id,
            GeneratedMessageJob.status == GeneratedMessageJobStatus.PENDING,
        ).first()
        if does_job_exist:
            continue

        gm_job: GeneratedMessageJob = create_generated_message_job(
            prospect_id=prospect_id, batch_id=batch_id
        )
        gm_job_id: int = gm_job.id

        generate_prospect_email.delay(
            prospect_id=prospect_id,
            email_schema_id=email_schema_id,
            batch_id=batch_id,
            gm_job_id=gm_job_id,
        )


@celery.task(bind=True, max_retries=3)
def generate_prospect_email(
    self, prospect_id: int, email_schema_id: int, batch_id: int, gm_job_id: int = None
):
    update_generated_message_job_status(
        gm_job_id, GeneratedMessageJobStatus.IN_PROGRESS
    )
    try:
        from src.research.linkedin.services import get_research_and_bullet_points_new

        get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)

        prospect: Prospect = Prospect.query.get(prospect_id)
        email_schema: EmailSchema = EmailSchema.query.get(email_schema_id)
        if not prospect:
            return False
        if not email_schema:
            return False

        prospect_email: ProspectEmail = ProspectEmail.query.filter(
            ProspectEmail.prospect_id == prospect_id,
            ProspectEmail.email_schema_id == email_schema_id,
        ).first()
        if prospect_email:
            return False

        archetype_id = prospect.archetype_id

        research: ResearchPayload = ResearchPayload.query.filter(
            ResearchPayload.prospect_id == prospect_id
        ).first()
        research_id = research.id

        research_points_list: list[ResearchPoints] = ResearchPoints.query.filter(
            ResearchPoints.research_payload_id == research_id
        ).all()

        NUM_GENERATIONS = 3  # number of ProspectEmail's to make
        perms = generate_batches_of_research_points(
            points=research_points_list, n=NUM_GENERATIONS, num_per_perm=3
        )

        for perm in perms:
            notes, research_points, _ = get_notes_and_points_from_perm(perm)
            prompt = generate_prompt(prospect_id=prospect_id, notes=notes)

            if len(research_points) == 0:
                update_generated_message_job_status(
                    gm_job_id, GeneratedMessageJobStatus.FAILED
                )
                continue

            personalized_first_line = get_personalized_first_line(
                archetype_id=archetype_id,
                model_type=GNLPModelType.EMAIL_FIRST_LINE,
                prompt=prompt,
                research_points=research_points,
                prospect_id=prospect_id,
                batch_id=batch_id,
            )

            create_prospect_email(
                email_schema_id=email_schema_id,
                prospect_id=prospect_id,
                personalized_first_line_id=personalized_first_line.id,
                batch_id=batch_id,
            )
    except Exception as e:
        update_generated_message_job_status(gm_job_id, GeneratedMessageJobStatus.FAILED)
        raise self.retry(exc=e, countdown=2**self.request.retries)

    update_generated_message_job_status(gm_job_id, GeneratedMessageJobStatus.COMPLETED)


def change_prospect_email_status(prospect_email_id: int, status: ProspectEmailStatus):
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect_email.email_status = status
    db.session.add(prospect_email)
    db.session.commit()

    personalized_first_line: GeneratedMessage = GeneratedMessage.query.get(
        prospect_email.personalized_first_line
    )
    if personalized_first_line:
        personalized_first_line.message_status = GeneratedMessageStatus[status.value]
        db.session.add(personalized_first_line)
        db.session.commit()

    return True


def mark_prospect_email_approved(prospect_email_id: int):
    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect_id = prospect_email.prospect_id
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_prospect_email_id = prospect_email.id
    db.session.add(prospect)
    db.session.commit()

    return change_prospect_email_status(
        prospect_email_id=prospect_email_id, status=ProspectEmailStatus.APPROVED
    )


def mark_prospect_email_sent(prospect_email_id: int):
    from model_import import ProspectStatus

    prospect: Prospect = Prospect.query.filter(
        Prospect.approved_prospect_email_id == prospect_email_id
    ).first()
    if prospect:
        prospect.status = ProspectStatus.SENT_OUTREACH
        db.session.add(prospect)
        db.session.commit()

    prospect_email: ProspectEmail = ProspectEmail.query.get(prospect_email_id)
    prospect_email.date_sent = datetime.datetime.now()
    db.session.add(prospect_email)
    db.session.commit()

    return change_prospect_email_status(
        prospect_email_id=prospect_email_id, status=ProspectEmailStatus.SENT
    )


def batch_mark_prospect_email_sent(prospect_ids: list):
    for prospect_id in prospect_ids:
        prospect: Prospect = Prospect.query.get(prospect_id)
        if prospect.approved_prospect_email_id:
            mark_prospect_email_sent(prospect.approved_prospect_email_id)
    return True


def wipe_prospect_email_and_generations_and_research(prospect_id: int):
    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.status != ProspectStatus.PROSPECTED:
        return False

    prospect_emails: list = ProspectEmail.query.filter(
        ProspectEmail.prospect_id == prospect_id
    ).all()

    prospect.approved_prospect_email_id = None
    prospect.approved_outreach_message_id = None
    db.session.add(prospect)
    db.session.commit()

    for prospect_email in prospect_emails:
        personalized_line = GeneratedMessage.query.get(
            prospect_email.personalized_first_line
        )
        db.session.delete(personalized_line)
        db.session.delete(prospect_email)
        db.session.commit()

    return True


def batch_approve_message_generations_by_heuristic(prospect_ids: int):
    from src.message_generation.services import (
        approve_message,
    )
    from app import db
    from tqdm import tqdm

    for prospect_id in tqdm(prospect_ids):
        data = db.session.execute(
            """
            select length(completion), *
            from generated_message
            where prospect_id = {prospect_id}
            order by abs(270 - length(completion)) asc
            limit 1;
        """.format(
                prospect_id=prospect_id
            )
        ).fetchall()
        if len(data) == 0:
            continue
        data = data[0]
        prospect: Prospect = Prospect.query.get(prospect_id)
        if prospect.approved_outreach_message_id != None:
            continue
        message_id = data["id"]
        approve_message(message_id=message_id)

    return True


def batch_disapprove_message_generations(prospect_ids: int):
    from src.message_generation.services import (
        disapprove_message,
    )
    from app import db
    from tqdm import tqdm

    for prospect_id in tqdm(prospect_ids):
        prospect: Prospect = Prospect.query.get(prospect_id)
        message_id = prospect.approved_outreach_message_id
        disapprove_message(message_id=message_id)

    return True


def create_generated_message_feedback(message_id: int, feedback_value: str):
    feedback: GeneratedMessageFeedback = GeneratedMessageFeedback(
        generated_message_id=message_id, feedback_value=feedback_value
    )
    db.session.add(feedback)
    db.session.commit()

    return True


def generate_cta_examples(company_name: str, persona: str, with_what: str):
    """
    company_name: Name of company
    persona: Name of persona
    with_what: What the company does for persona
    """
    import os

    openai.api_key = os.getenv("OPENAI_KEY")

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=(
            """
Make 6 CTAs that are comma separated for the company.
    
Example: Curative helps healthcare leaders with getting access to top physicians looking for new opportunities and achieve staffing goals.
Output:
- [Feedback] I wanted to get your thoughts on a staffing solution I'm building for providers - open to chat?
- [Problem] Would love to talk about what issues you're seeing in provider staffing.
- [Priority] Is staffing a priority for your health system? Would love to see if Curative can help.
- [Persona] Since you're a leader in your health system, would love to see if Curative is helpful for staffing.
- [Solution] Given how competitive hiring providers is, and our access to them, would love to connect!
- [Company] Have you heard of Curative? Would love to tell you about how we help with provider staffing.

{company_name} helps {persona} with {with_what}
-
""".format(
                company_name=company_name, persona=persona, with_what=with_what
            )
        ),
        temperature=0,
        max_tokens=500,
        top_p=1,
        frequency_penalty=0.2,
        presence_penalty=0,
    )

    ctas = []

    options = response["choices"][0]["text"].split("\n- ")
    for option in options:
        tag, cta = option.split("] ")
        tag = tag[1:]

        ctas.append({"tag": tag, "cta": cta})

    return ctas


def get_named_entities(string: str):
    """
    Get named entities from a string
    """
    sentence = Sentence(string)
    tagger.predict(sentence)

    entites = []
    for entity in sentence.get_spans("ner"):
        entites.append(entity)

    return entites
