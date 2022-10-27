from src.ml.adverserial_ai import get_adversarial_ai_approval
from src.ml.models import GNLPModelType
from src.research.models import ResearchPayload, ResearchPoints
from src.utils.random_string import generate_random_alphanumeric
from ..ml.fine_tuned_models import (
    get_basic_openai_completion,
    get_completion,
    get_custom_completion_for_client,
)
from ..utils.abstract.attr_utils import deep_get
import random
from app import db, celery
from tqdm import tqdm


def research_and_generate_outreaches_for_prospect_list(
    prospect_ids: list, cta_prompt: str = None
):
    batch_id = generate_random_alphanumeric(36)
    for prospect_id in tqdm(prospect_ids):
        research_and_generate_outreaches_for_prospect.delay(
            prospect_id=prospect_id, cta_prompt=cta_prompt, batch_id=batch_id
        )

    return True


@celery.task
def research_and_generate_outreaches_for_prospect(
    prospect_id: int, batch_id: str, cta_prompt: str = None
):
    from src.research.linkedin.services import get_research_and_bullet_points_new

    get_research_and_bullet_points_new(prospect_id=prospect_id, test_mode=False)
    generate_outreaches_for_batch_of_prospects(
        prospect_list=[prospect_id], cta_prompt=cta_prompt, batch_id=batch_id
    )


def generate_prompt(linkedin_payload: any, notes: str = ""):
    bio_data = {
        "full_name": deep_get(linkedin_payload, "personal.first_name")
        + " "
        + deep_get(linkedin_payload, "personal.last_name"),
        "industry": deep_get(linkedin_payload, "personal.industry"),
        "company": deep_get(linkedin_payload, "company.details.name"),
        "title": deep_get(
            linkedin_payload, "personal.position_groups.0.profile_positions.0.title"
        ),
        "notes": notes,
        "cleaned_bio": deep_get(linkedin_payload, "personal.summary"),
    }
    prompt = "name: {full_name}<>industry: {industry}<>company: {company}<>title: {title}<>notes: {notes}<>response:".format(
        **bio_data
    )

    return prompt


def generate_prompt_permutations_from_notes(notes: dict, n: int = 1):
    perms = []
    notes = [notes[key] for key in notes.keys()]

    for i in range(n):
        sample = ["- " + x for x in random.sample(notes, 2)]
        perms.append(" ".join(sample))

    return perms


def generate_batches_of_research_points(points: list, n: int = 1):
    perms = []
    for i in range(n):
        sample = [x for x in random.sample(points, 2)]
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


def generate_outreaches_new(prospect_id: int, batch_id: str, cta_prompt: str = None):
    from model_import import GeneratedMessage, GeneratedMessageStatus, Prospect

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
        d = ["-" + x.value for x in perm]
        if cta_prompt:
            d.append("-" + cta_prompt)
        notes = "\n".join(d)

        research_points = [x.id for x in perm]

        prompt = generate_prompt(linkedin_payload=research.payload, notes=notes)

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
            )
            db.session.add(message)
            db.session.commit()

    return outreaches


def generate_outreaches_for_batch_of_prospects(
    prospect_list: list, batch_id: str, cta_prompt: str = None
):
    # todo(Aakash) add batch here
    for prospect_id in tqdm(prospect_list):
        try:
            generate_outreaches_new(
                prospect_id=prospect_id, cta_prompt=cta_prompt, batch_id=batch_id
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
    message.message_status = GeneratedMessageStatus.APPROVED
    db.session.add(message)

    prospect_id = message.prospect_id
    prospect: Prospect = Prospect.query.get(prospect_id)
    prospect.approved_outreach_message_id = message.id
    db.session.add(prospect)

    db.session.commit()

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
        )
        db.session.add(gm)
        db.session.commit()

    return True
