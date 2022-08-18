from ..ml.fine_tuned_models import get_completion
from ..utils.abstract.attr_utils import deep_get
import random

def generate_prompt(linkedin_payload: any, notes: str=''):
    bio_data = {
        'full_name': deep_get(linkedin_payload, 'personal.first_name') + " " + deep_get(linkedin_payload, 'personal.last_name'),
        'industry': deep_get(linkedin_payload, 'personal.industry'),
        'company': deep_get(linkedin_payload, 'company.details.name'),
        'title': deep_get(linkedin_payload, 'personal.position_groups.0.profile_positions.0.title'),
        'notes': notes,
        'cleaned_bio': deep_get(linkedin_payload, 'personal.summary')
    }
    prompt = "name: {full_name}<>industry: {industry}<>company: {company}<>title: {title}<>notes: {notes}<>bio: {cleaned_bio}<>response:".format(**bio_data)

    return prompt

def generate_prompt_permutations_from_notes(notes: dict, n: int = 1):
    perms = []
    notes = [notes[key] for key in notes.keys()]

    for i in range(n):
        sample = ['- ' + x for x in random.sample(notes, 2)]
        perms.append('\n'.join(sample))
    
    return perms

def generate_outreaches(research_and_bullets: dict, num_options: int = 1):
    profile = research_and_bullets['raw_data']
    notes = research_and_bullets['bullets']

    perms = generate_prompt_permutations_from_notes(
        notes=notes,
        n=num_options
    )

    outreaches = []
    for perm in perms:
        prompt = generate_prompt(
            linkedin_payload=profile,
            notes=perm
        )
        completions = get_completion(
            bullet_model_id='baseline_generation',
            prompt=prompt,
            max_tokens=90,
            n=2
        )
    
        for completion in completions:
            outreaches.append(completion)

    return outreaches