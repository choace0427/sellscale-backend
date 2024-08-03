from typing import Optional

class SequenceAutoGenerationParameters:
    def __init__(self, find_sample_prospects=False, write_email_sequence_draft=False, write_li_sequence_draft=False,
                 email_sequence_opened=False, email_sequence_keywords=None, li_sequence_opened=False, li_general_angle="",
                 email_general_angle="", li_sequence_keywords=None, li_asset_ingestor="", li_cta_generator=False, li_pain_point="",
                 li_sequence_state=None, email_sequence_state=None):
        self.find_sample_prospects = find_sample_prospects
        self.write_email_sequence_draft = write_email_sequence_draft
        self.write_li_sequence_draft = write_li_sequence_draft
        self.email_sequence_opened = email_sequence_opened
        self.email_sequence_keywords = email_sequence_keywords if email_sequence_keywords else []
        self.li_sequence_opened = li_sequence_opened
        self.li_general_angle = li_general_angle
        self.email_general_angle = email_general_angle
        self.li_sequence_keywords = li_sequence_keywords if li_sequence_keywords else []
        self.li_asset_ingestor = li_asset_ingestor
        self.li_cta_generator = li_cta_generator
        self.li_pain_point = li_pain_point
        self.li_sequence_state = SequenceState(
            how_it_works=li_sequence_state.get("howItWorks", False),
            vary_intro_messages=li_sequence_state.get("varyIntroMessages", False),
            breakup_message=li_sequence_state.get("breakupMessage", False),
            unique_offer=li_sequence_state.get("uniqueOffer", False),
            conference_outreach=li_sequence_state.get("conferenceOutreach", False),
            city_chat=li_sequence_state.get("cityChat", False),
            former_work_alum=li_sequence_state.get("formerWorkAlum", False),
            feedback_based=li_sequence_state.get("feedbackBased", False)
        ) if li_sequence_state else SequenceState()
        self.email_sequence_state = SequenceState(
            how_it_works=email_sequence_state.get("howItWorks", False),
            vary_intro_messages=email_sequence_state.get("varyIntroMessages", False),
            breakup_message=email_sequence_state.get("breakupMessage", False),
            unique_offer=email_sequence_state.get("uniqueOffer", False),
            conference_outreach=email_sequence_state.get("conferenceOutreach", False),
            city_chat=email_sequence_state.get("cityChat", False),
            former_work_alum=email_sequence_state.get("formerWorkAlum", False),
            feedback_based=email_sequence_state.get("feedbackBased", False)
        ) if email_sequence_state else SequenceState()

class SequenceState:
    def __init__(self, how_it_works=False, vary_intro_messages=False, breakup_message=False, unique_offer=False,
                 conference_outreach=False, city_chat=False, former_work_alum=False, feedback_based=False):
        self.how_it_works = how_it_works
        self.vary_intro_messages = vary_intro_messages
        self.breakup_message = breakup_message
        self.unique_offer = unique_offer
        self.conference_outreach = conference_outreach
        self.city_chat = city_chat
        self.former_work_alum = former_work_alum
        self.feedback_based = feedback_based

def initialize_auto_generation_payload(auto_generation_payload: Optional[dict]) -> SequenceAutoGenerationParameters:
    default_payload = {
        "find_sample_prospects": False,
        "write_email_sequence_draft": False,
        "write_li_sequence_draft": False,
        "email_sequence_opened": False,
        "email_sequence_keywords": [],
        "li_sequence_opened": False,
        "li_general_angle": "",
        "email_general_angle": "",
        "li_sequence_keywords": [],
        "li_asset_ingestor": "",
        "li_cta_generator": False,
        "li_pain_point": "",
        "li_sequence_state": {
            "how_it_works": False,
            "vary_intro_messages": False,
            "breakup_message": False,
            "unique_offer": False,
            "conference_outreach": False,
            "city_chat": False,
            "former_work_alum": False,
            "feedback_based": False
        },
        "email_sequence_state": {
            "how_it_works": False,
            "vary_intro_messages": False,
            "breakup_message": False,
            "unique_offer": False,
            "conference_outreach": False,
            "city_chat": False,
            "former_work_alum": False,
            "feedback_based": False
        }
    }

    if auto_generation_payload is None:
        auto_generation_payload = default_payload
    else:
        for key, value in default_payload.items():
            if key not in auto_generation_payload:
                auto_generation_payload[key] = value
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if sub_key not in auto_generation_payload[key]:
                        auto_generation_payload[key][sub_key] = sub_value

    print("Auto Generation Payload Parameters:")
    print(f"Find Sample Prospects: {auto_generation_payload.get('findSampleProspects')}")
    print(f"Write Email Sequence Draft: {auto_generation_payload.get('writeEmailSequenceDraft')}")
    print(f"Write LinkedIn Sequence Draft: {auto_generation_payload.get('writeLISequenceDraft')}")
    print(f"Email Sequence Opened: {auto_generation_payload.get('emailSequenceOpened')}")
    print(f"Email Sequence Keywords: {auto_generation_payload.get('emailSequenceKeywords')}")
    print(f"LinkedIn Sequence Opened: {auto_generation_payload.get('liSequenceOpened')}")
    print(f"LinkedIn General Angle: {auto_generation_payload.get('liGeneralAngle')}")
    print(f"Email General Angle: {auto_generation_payload.get('emailGeneralAngle')}")
    print(f"LinkedIn Sequence Keywords: {auto_generation_payload.get('liSequenceKeywords')}")
    print(f"LinkedIn Asset Ingestor: {auto_generation_payload.get('liAssetIngestor')}")
    print(f"LinkedIn CTA Generator: {auto_generation_payload.get('liCtaGenerator')}")
    print(f"LinkedIn Pain Point: {auto_generation_payload.get('liPainPoint')}")
    print("LinkedIn Sequence State:")
    for key, value in auto_generation_payload.get('liSequenceState', {}).items():
        print(f"  {key}: {value}")
    print("Email Sequence State:")
    for key, value in auto_generation_payload.get('emailSequenceState', {}).items():
        print(f"  {key}: {value}")
    return SequenceAutoGenerationParameters(
        find_sample_prospects=auto_generation_payload.get('findSampleProspects'),
        write_email_sequence_draft=auto_generation_payload.get('writeEmailSequenceDraft'),
        write_li_sequence_draft=auto_generation_payload.get('writeLISequenceDraft'),
        email_sequence_opened=auto_generation_payload.get('emailSequenceOpened'),
        email_sequence_keywords=auto_generation_payload.get('emailSequenceKeywords'),
        li_sequence_opened=auto_generation_payload.get('liSequenceOpened'),
        li_general_angle=auto_generation_payload.get('liGeneralAngle'),
        email_general_angle=auto_generation_payload.get('emailGeneralAngle'),
        li_sequence_keywords=auto_generation_payload.get('liSequenceKeywords'),
        li_asset_ingestor=auto_generation_payload.get('liAssetIngestor'),
        li_cta_generator=auto_generation_payload.get('liCtaGenerator'),
        li_pain_point=auto_generation_payload.get('liPainPoint'),
        li_sequence_state=auto_generation_payload.get('liSequenceState'),
        email_sequence_state=auto_generation_payload.get('emailSequenceState')
    )

def generate_email_sequence_prompt(auto_generation_parameters: SequenceAutoGenerationParameters) -> str:
    if not auto_generation_parameters:
        return "No parameters provided for email sequence generation."

    prompt = ""
    
    if auto_generation_parameters.email_general_angle:
        prompt += f"Here is the general angle for the sequence: {auto_generation_parameters.email_general_angle}\n"
    
    if auto_generation_parameters.email_sequence_state and any(vars(auto_generation_parameters.email_sequence_state).values()):
        prompt += "I have selected the following parameters for email sequence generations:\n"
        if auto_generation_parameters.email_sequence_state.how_it_works:
            prompt += "Please state How it works\n"
        if auto_generation_parameters.email_sequence_state.vary_intro_messages:
            prompt += "Please Vary the intro messages\n"
        if auto_generation_parameters.email_sequence_state.breakup_message:
            prompt += "Please include a Breakup message\n"
        if auto_generation_parameters.email_sequence_state.unique_offer:
            prompt += "Please include a Unique offer\n"
        if auto_generation_parameters.email_sequence_state.conference_outreach:
            prompt += "Conference outreach\n"
        if auto_generation_parameters.email_sequence_state.city_chat:
            prompt += "City chat\n"
        if auto_generation_parameters.email_sequence_state.former_work_alum:
            prompt += "Former work alum\n"
        if auto_generation_parameters.email_sequence_state.feedback_based:
            prompt += "Feedback based\n"

    if auto_generation_parameters.email_sequence_keywords:
        prompt += 'These are the keywords you absolutely have to include: ' + ', '.join(auto_generation_parameters.email_sequence_keywords) + '\n'

    print('Email Sequence Prompt:', prompt)
    return prompt

def generate_linkedin_sequence_prompt(auto_generation_parameters: SequenceAutoGenerationParameters) -> str:
    if not auto_generation_parameters:
        return "No parameters provided for LinkedIn sequence generation."

    prompt = ""
    
    if auto_generation_parameters.li_general_angle:
        prompt += f"Here is the general angle for the sequence: {auto_generation_parameters.li_general_angle}\n"
    
    if auto_generation_parameters.li_pain_point:
        prompt += f"Here is a pain point you could mention: {auto_generation_parameters.li_pain_point}\n"
    
    if auto_generation_parameters.li_sequence_state and any(vars(auto_generation_parameters.li_sequence_state).values()):
        prompt += "I have selected the following parameters for LinkedIn sequence generations:\n"
        if auto_generation_parameters.li_sequence_state.how_it_works:
            prompt += "Please state How it works\n"
        if auto_generation_parameters.li_sequence_state.vary_intro_messages:
            prompt += "Please Vary the intro messages\n"
        if auto_generation_parameters.li_sequence_state.breakup_message:
            prompt += "Please include a Breakup message\n"
        if auto_generation_parameters.li_sequence_state.unique_offer:
            prompt += "Please include a Unique offer\n"
        if auto_generation_parameters.li_sequence_state.conference_outreach:
            prompt += "Conference outreach\n"
        if auto_generation_parameters.li_sequence_state.city_chat:
            prompt += "City chat\n"
        if auto_generation_parameters.li_sequence_state.former_work_alum:
            prompt += "Former work alum\n"
        if auto_generation_parameters.li_sequence_state.feedback_based:
            prompt += "Feedback based\n"

    if auto_generation_parameters.li_sequence_keywords:
        prompt += 'These are the keywords you absolutely have to include: ' + ', '.join(auto_generation_parameters.li_sequence_keywords) + '\n'

    print('LinkedIn Sequence Prompt:', prompt)
    return prompt