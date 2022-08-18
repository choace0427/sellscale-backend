from flask import Blueprint, jsonify

from ..message_generation.services import generate_outreaches, generate_prompt, generate_prompt_permutations_from_notes
from .linkedin.services import get_research_and_bullet_points

RESEARCH_BLUEPRINT = Blueprint('research', __name__)


@RESEARCH_BLUEPRINT.route("/<linkedin_id>")
def research_linkedin(linkedin_id: str):
    # ids = ['aaadesara', 'vsodera', 'alisohani', 'vhiremath4', 'katherineliu28', 'hilaryshirazi', 'helentongli', 'wang-alicia', 'omar-palacios-3991729', 'metibasiri', 'brettmayfield', 'haleymbryant', 'ravenjiang', 'abhishek--agrawal', 'christianlemp', 'guo-annie', 'leannyuen', 'aliisa-rosenthal', 'ryan-hollander-75222451', 'pdgoodman', 'ericastuart77', 'ngwangsa', 'ankushagrawal94', 'christosbakis', 'danjiao', 'judyban', 'johnhanzhao', 'rohan-kumar-1539591b2', 'hyewonpark96', 'jcqlnezhang', 'chenglong-cai-067161196', 'justke', 'hamravatkar']
    # payload = []
    # for i in ids:
    #     try:
    #         payload.append(get_research_bullet_points(profile_id=i, test_mode=False)['recent_recommendation']['prompt'])
    #     except:
    #         pass
    # return {'data': payload}

    data = get_research_and_bullet_points(profile_id=linkedin_id, test_mode=False)
    outreaches = generate_outreaches(
        research_and_bullets=data,
        num_options=4
    )

    return jsonify({
        'source': data,
        'outreaches': outreaches
    })