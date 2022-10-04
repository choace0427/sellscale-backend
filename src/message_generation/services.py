from src.research.models import ResearchPayload, ResearchPoints
from ..ml.fine_tuned_models import get_completion
from ..utils.abstract.attr_utils import deep_get
import random
from app import db
from tqdm import tqdm


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
    prompt = "name: {full_name}<>industry: {industry}<>company: {company}<>title: {title}<>notes: {notes}<>bio: {cleaned_bio}<>response:".format(
        **bio_data
    )

    return prompt


def generate_prompt_permutations_from_notes(notes: dict, n: int = 1):
    perms = []
    notes = [notes[key] for key in notes.keys()]

    for i in range(n):
        sample = ["- " + x for x in random.sample(notes, 2)]
        perms.append("\n".join(sample))

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


def generate_outreaches_new(prospect_id: int):
    from model_import import GeneratedMessage, GeneratedMessageStatus

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
        notes = "\n".join(d)

        research_points = [x.id for x in perm]

        prompt = generate_prompt(linkedin_payload=research.payload, notes=notes)
        completions = get_completion(
            bullet_model_id="baseline_generation", prompt=prompt, max_tokens=90, n=2
        )

        for completion in completions:
            outreaches.append(completion)

            message: GeneratedMessage = GeneratedMessage(
                prospect_id=prospect_id,
                gnlp_model_id=5,
                research_points=research_points,
                prompt=prompt,
                completion=completion,
                message_status=GeneratedMessageStatus.DRAFT,
            )
            db.session.add(message)
            db.session.commit()

    return outreaches


def generate_outreaches_for_batch_of_prospects(prospect_list: list):
    for prospect_id in tqdm(prospect_list):
        try:
            generate_outreaches_new(prospect_id=prospect_id)
        except Exception as e:
            print(e)
            pass

    return True


def update_message(message_id: int, update: str):
    from model_import import GeneratedMessage

    message: GeneratedMessage = GeneratedMessage.query.get(message_id)
    message.completion = update
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
