import random
from src.client.models import (
    ClientArchetype,
    ClientAssetType,
    ClientAssets,
    ClientSDR,
    Client,
    DemoFeedback,
)
from model_import import Individual
from src.client.archetype.services_client_archetype import get_archetype_assets
from src.ml.services import get_text_generation
from src.utils.datetime.dateutils import get_current_time_casual
from src.individual.services import parse_work_history
import re
from src.utils.string.string_utils import rank_number

ASSET_AMOUNT = 1


def get_sdr_prompting_context_info(client_sdr_id: int):

    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(sdr.client_id)
    individual: Individual = Individual.query.get(sdr.individual_id)

    sdr_name = f"""Your Name: {sdr.name}"""
    sdr_email = (
        f"""Your Email: {individual.email}""" if individual and individual.email else ""
    )
    sdr_phone = (
        f"""Your Phone #: {individual.phone}"""
        if individual and individual.phone
        else ""
    )
    sdr_title = (
        f"""Your Title: {individual.title}""" if individual and individual.title else ""
    )
    sdr_bio = f"""Your Bio: {individual.bio}""" if individual and individual.bio else ""
    sdr_job_description = (
        f"""Your Job Description: {individual.recent_job_description}"""
        if individual and individual.recent_job_description
        else ""
    )
    sdr_industry = (
        f"""Your Industry: {individual.industry}"""
        if individual and individual.industry
        else ""
    )
    sdr_location = (
        f"""Your Location: {individual.location.get("default")}"""
        if individual and individual.location and individual.location.get("default")
        else ""
    )
    sdr_school = (
        f"""Your School: {individual.recent_education_school}"""
        if individual and individual.recent_education_school
        else ""
    )
    sdr_degree = (
        f"""Your Degree: {individual.recent_education_degree}"""
        if individual and individual.recent_education_degree
        else ""
    )
    sdr_education_field = (
        f"""Your Education Field: {individual.recent_education_field}"""
        if individual and individual.recent_education_field
        else ""
    )
    sdr_education_start_date = (
        f"""Your Education Start Date: {individual.recent_education_start_date}"""
        if individual and individual.recent_education_start_date
        else ""
    )
    sdr_education_end_date = (
        f"""Your Education End Date: {individual.recent_education_end_date}"""
        if individual and individual.recent_education_end_date
        else ""
    )

    client_name = f"""Your Company Name: {client.company}""" if client.company else ""
    client_tagline = (
        f"""You Company Tagline: {client.tagline}""" if client.tagline else ""
    )
    client_description = (
        f"""Your Company Description: {client.description}"""
        if client.description
        else ""
    )
    client_key_value_props = (
        f"""Your Company Key Value Props: {client.value_prop_key_points}"""
        if client.value_prop_key_points
        else ""
    )
    client_mission = (
        f"""Your Company Mission: {client.mission}""" if client.mission else ""
    )
    client_impressive_facts = (
        f"""Your Company Impressive Facts: {client.impressive_facts}"""
        if client.impressive_facts
        else ""
    )
    sdr_work_history = (
        "Your Work History (most recent first): \n"
        + "\n".join(
            [
                f"History - Company Name: {work.get('company_name')}, Title: {work.get('title')}, Start Date: {work.get('start_Date', '?')}, End Date: {work.get('start_Date', '?')}"
                for work in parse_work_history(individual.work_history)
            ]
        )
        if individual and individual.work_history
        else ""
    )

    day, day_of_month, month, year = get_current_time_casual(sdr.timezone)

    context_info = f"""
Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Current Time: {day}, {day_of_month}, {month}, {year}
    {sdr_name}
    {sdr_email}
    {sdr_phone}
    {sdr_title}
    {sdr_bio}
    {sdr_job_description}
    {sdr_industry}
    {sdr_location}
    {sdr_school}
    {sdr_degree}
    {sdr_education_field}
    {sdr_education_start_date}
    {sdr_education_end_date}
    {client_name}
    {client_tagline}
    {client_description}
    {client_key_value_props}
    {client_mission}
    {client_impressive_facts}
    {sdr_work_history}
    """.strip()

    return context_info


def generate_sequence(
    client_id: int,
    archetype_id: int,
    sequence_type: str,
    num_steps: int,
    additional_prompting: str,
):

    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    context_info = get_sdr_prompting_context_info(archetype.client_sdr_id)

    raw_assets = get_archetype_assets(archetype_id)
    all_assets = [
        {
            "id": asset.get("id"),
            "title": asset.get("asset_key"),
            "value": asset.get("asset_value"),
            "tag": (
                asset.get("asset_tags", [])[0]
                if len(asset.get("asset_tags", [])) > 0
                else ""
            ),
        }
        for asset in raw_assets
    ]

    output = []
    if sequence_type == "EMAIL":

        for i in range(1, num_steps):

            assets = random.sample(
                all_assets,
                min(ASSET_AMOUNT, len(all_assets)),
            )
            assets_str = "## Assets: \n" + "\n\n".join(
                [
                    f"Title: {asset.get('title')}\nValue: {asset.get('value')}\nTag: {asset.get('tag')}"
                    for asset in assets
                ]
            )

            if i == 1:
                output.append(
                    {
                        "result": clean_output(
                            generate_email_initial(
                                client_id=client_id,
                                archetype_id=archetype_id,
                                context_info=context_info,
                                assets_str=assets_str,
                                additional_prompting=additional_prompting,
                            )
                        ),
                        "assets": assets,
                        "step_num": i,
                    }
                )
            else:
                print(output)

                output.append(
                    {
                        "result": clean_output(
                            generate_email_follow_up(
                                client_id=client_id,
                                archetype_id=archetype_id,
                                step_num=i,
                                context_info=context_info,
                                assets_str=assets_str,
                                additional_prompting=additional_prompting,
                                previous_emails_str="",
                            )
                        ),
                        "assets": assets,
                        "step_num": i,
                    }
                )

    else:
        output = []

    return output


def generate_email_initial(
    client_id: int,
    archetype_id: int,
    context_info: str,
    assets_str: str,
    additional_prompting: str,
):

    prompt = f"""
    
You are working to create a cold email in a sequence for generative outreach to prospects.
The email should use different assets that have a unique value prop, pain point, case study, unique facts, etc that can be used in to make that email stand out. It should also have a particular angle or approach to the outreach.
When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.

{additional_prompting if additional_prompting else ""}

Here's some previous examples of what you're expected to generate.
# Previous Example 1 #
-------------------------------------------------------------

Please generate a cold email outline for generative outreach to prospects.

{get_email_example(1, 1)}

-------------------------------------------------------------

# Previous Example 2 #
-------------------------------------------------------------

Please generate a cold email outline for generative outreach to prospects.


{get_email_example(2, 1)}

-------------------------------------------------------------

# Previous Example 3 #
-------------------------------------------------------------

Please generate a cold email outline for generative outreach to prospects.

{get_email_example(3, 1)}

-------------------------------------------------------------

# Your Turn #
Okay now it's your turn to generate an email. Good luck! Remember to keep your email short and concise and stay off the spam folder!



Please generate a cold email outline for generative outreach to prospects.

{context_info}


{assets_str}


## Output:

    """.strip()

    print(prompt)

    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-4",  # -turbo-preview
            max_tokens=4000,
            type="EMAIL",
            temperature=0.85,
            use_cache=False,
        )
        or ""
    )

    return completion


def generate_email_follow_up(
    client_id: int,
    archetype_id: int,
    step_num: int,
    context_info: str,
    assets_str: str,
    additional_prompting: str,
    previous_emails_str: str,
):

    prompt = f"""
    
You are working to create a follow up email in a sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.
The email should use different assets that have a unique value prop, pain point, case study, unique facts, etc that can be used in to make that email stand out. Each should also have a different angle or approach to the outreach.
When fitting, feel free to include square brackets in areas where you'd want to include personalized information about the prospect and their company - this will be filled in by someone else later.

{additional_prompting if additional_prompting else ""}

Here's some previous examples of what you're expected to generate.
# Previous Example 1 #
-------------------------------------------------------------

Please generate the {rank_number(step_num)} email in the sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.

{get_email_example(1, step_num)}

-------------------------------------------------------------

# Previous Example 2 #
-------------------------------------------------------------

Please generate the {rank_number(step_num)} email in the sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.

{get_email_example(2, step_num)}

-------------------------------------------------------------

# Previous Example 3 #
-------------------------------------------------------------

Please generate the {rank_number(step_num)} email in the sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.

{get_email_example(3, step_num)}

-------------------------------------------------------------

# Your Turn #
Okay now it's your turn to generate an email. Good luck! Remember to keep your email short and concise and stay off the spam folder!



Please generate the {rank_number(step_num)} email in the sequence for generative outreach to prospects. The first email is a cold email, and the following emails are follow-ups to the cold email since the prospect didn't respond.

{context_info}

{previous_emails_str}

{assets_str}


## Output:

    """.strip()

    print(prompt)

    completion = (
        get_text_generation(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-4-turbo-preview",  # -turbo-preview
            max_tokens=4000,
            type="EMAIL",
            temperature=0.85,
            use_cache=False,
        )
        or ""
    )

    return completion


def clean_output(output: str):
    parts = output.split("\n### Angle")
    email_raw = parts[0].strip()
    email_parts = email_raw.split("### Email")
    email = email_parts[1].strip() if len(email_parts) > 1 else email_parts[0].strip()
    angle = parts[1].strip() if len(parts) > 1 else "Unknown Angle"

    # Remove potential subject line
    email = re.sub(
        r"^\W*Subject:.+?\n", "", email, 1, flags=re.MULTILINE | re.IGNORECASE
    )

    # Remove potential generation fluff
    email = re.sub(r"^\W+", "", email)
    angle = re.sub(r"^\W+", "", angle)

    return {"message": email, "angle": angle}


def get_email_example(example_num: int, step_num: int):

    def get_example_prompt():
        prompt = ""

        for i in range(1, step_num):

            title = ""

            if i == 1:
                title = "Initial Cold Email"
            else:
                title = f"{rank_number(i)} Follow-Up Email"

            example = get_email_step_example(example_num, i)
            if example is None:
                continue

            prompt += f"""

### {title}:
-----
{example}

            """

        return prompt.strip()

    return f"""
      
{get_example_context_info(example_num)}
      
{get_example_prompt()}
      
      """.strip()


def get_example_context_info(example_num: int):

    # Hristina Bell
    if example_num == 1:
        return """
      
Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Current Time: Wednesday, 3rd, April, 2024
    Your Name: Hristina Bell
    
    
    Your Title: GTM at Doppler | At Doppler, we are building the first SecretOps platform to make it easier for developers to manage secrets at scale and empower teams to be more productive and secure.
    Your Bio: Over my career, I have had the great fortune to help grow Fortune 50 companies as well as 🚀 startups, alongside highly talented professionals and customers of all sizes spanning my years at MUFG, IBM, Salesforce, Scale AI, and Doppler. I am passionate about delivering customer value, building lasting relationships, creating new categories, and going above and beyond to deliver results.

In my personal time, I enjoy spending time with family and friends, reading, mentoring, podcasts, exercising, music and nature.

📨 hbencheva@gmail.com
📱 925.348.5239
    Your Job Description: Building the account management and success motions at Doppler.
    Your Industry: Information Technology & Services
    Your Location: San Francisco, California, United States
    Your School: San Francisco State University
    Your Degree: Master of Business Administration - MBA
    Your Education Field: Marketing
    
    
    Your Company Name: Doppler
    You Company Tagline: Doppler is the uncomplicated way to sync, manage, orchestrate, and rotate secrets across any environment or app config with easy to use tools.
    Your Company Description: Doppler enables developers and security teams to keep their secrets and app configuration in sync and secure across devices, environments, and team members.
    Your Company Key Value Props: Collaborate Together:
Your team's encrypted source of truth. Organize your secrets across projects and environments. The scary days of sharing secrets over Slack, email, git and zip files are over. After adding a secret, your team and their apps have it instantly.

Automate Everything:
The best developers automate the pain away. Create references to frequently used secrets in Doppler. When they need to change, you only need to update them once.

Works Everywhere:
Use your secrets in Docker, Serverless, or anywhere else. We work where you work.
Go live in minutes, not months. As your stack evolves, Doppler remains simple.

Boost Your Productivity:
Like git, the Doppler CLI smartly knows which secrets to fetch based on the project directory you are in. Gone are the futile days of trying to keep ENV files in sync!

Version Everything:
Add confidence to a brittle part of your stack with immutable history with optional Slack and Microsoft Teams alerts when things change.
Roll back broken changes with a single click or through our robust API and CLI.
    Your Company Mission: Secure the world's secrets.
    Your Company Impressive Facts: 31,500+ Startups and Enterprises
10.5B+ Secrets Read per Month
99.99% Historical Annual Uptime
    Your Work History (most recent first): 
History - Company Name: Doppler, Title: GTM Leader - Sales & Success, Start Date: ?, End Date: ?
History - Company Name: Doppler, Title: Sales Lead - GTM - Sr Account Executive, Start Date: ?, End Date: ?
History - Company Name: Scale AI, Title: Strategic Account Executive, Start Date: ?, End Date: ?
History - Company Name: Salesforce, Title: Account Executive - General Business, Start Date: ?, End Date: ?
History - Company Name: IBM, Title: Enterprise Client Executive, Start Date: ?, End Date: ?
History - Company Name: IBM, Title: Client Executive - Integrated accounts, Start Date: ?, End Date: ?
History - Company Name: MUFG, Title: Customer Success and Operations Lead, Start Date: ?, End Date: ?
History - Company Name: MUFG, Title: Customer Success / Relationship Manager, Start Date: ?, End Date: ?
History - Company Name: MUFG, Title: Securities Lending, Start Date: ?, End Date: ?
History - Company Name: East West Bank, Title: Treasury Analyst, Start Date: ?, End Date: ?
  
      """.strip()

    # Ishan Sharma
    if example_num == 2:
        return """
      
Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Current Time: Monday, 1st, April, 2024
    Your Name: Ishan Sharma
    Your Email: ishan@sellscale.com
    
    Your Title: Co-founder & CEO @ SellScale
    Your Bio: I'm a Cal alum interested in tech, government, and entrepreneurship. On the side, you can catch me hacking together side projects, longboarding down the Berkeley hills, drumming to classic rock, and watching hours of TED Talks.
 sharmaishan.com
    Your Job Description: Growing companies with sales AGI
    Your Industry: Computer Software
    Your Location: San Francisco Bay Area
    Your School: University of California, Berkeley
    Your Degree: Bachelor's of Science
    Your Education Field: Economics/Business Admin
    
    
    Your Company Name: DailyDropout.fyi
    You Company Tagline: Premium startup newsletter with 130k+ subscribers
    Your Company Description: DailyDropout.fyi is a startup firm with a newsletter of 130k+ subscribers. Readers include investors from top firms like Sequoia, Sequoia, Lightspeed, and more. We've featured 100s of startups, many of which went on to raise millions in venture capital. Work to feature interesting companies for investors and future employees.
    
    
    
    Your Work History (most recent first): 
History - Company Name: SellScale, Title: Co-Founder & CEO, Start Date: ?, End Date: ?
History - Company Name: Athelas, Title: Business Operations, Start Date: ?, End Date: ?
History - Company Name: McKinsey & Company, Title: Business Analyst, Start Date: ?, End Date: ?
History - Company Name: Slack, Title: Product Marketing Manager, Start Date: ?, End Date: ?
History - Company Name: Lightspeed Venture Partners, Title: Fellow, Start Date: ?, End Date: ?
History - Company Name: HS Mixers, Title: Small Business Owner, Start Date: ?, End Date: ?
History - Company Name: U.S. House of Representatives, Title: Congressional Intern, Start Date: ?, End Date: ?
History - Company Name: Cupertino High School, Title: The M&M Project, Start Date: ?, End Date: ?

      """.strip()

    # Shivang Patel
    if example_num == 3:
        return """

Here's some contextual info about you. Feel free to reference this when appropriate.
    
## Context:
    Current Time: Thursday, 14th, March, 2024
    Your Name: Shivang Patel
    
    
    Your Title: Where today’s most important questions find the world’s most knowledgeable minds.
    Your Bio: Experienced Account Executive with a demonstrated history of working in the information technology and healthcare industries. Skilled in Strategy, Sales, Management, Healthcare, and IT.
    
    Your Industry: Information Technology & Services
    Your Location: Houston, Texas, United States
    Your School: University of Houston-Clear Lake
    Your Degree: MHA/MBA
    
    
    
    Your Company Name: NewtonX
    You Company Tagline: The leading B2B market research company connecting decision makers with verified expert insights they can trust.
    Your Company Description: NewtonX is the only B2B market research company that connects decision makers with verified expert insights they can trust. We are doing quantitative and qualitative research leveraging our AI-powered recruitment technology that has the highest scale, quality, and accuracy in the market. Many leading clients like Salesforce or Microsoft have done large scale A/B tests between our data and competitor data which showed that their fraud rates are >30% while ours are <1% across the board. We empower business decision makers to make product, brand, go-to-market, M&A and investment decisions in confide. 
    Your Company Key Value Props: 1. The best research: qualitative & quantitative market research with custom recruited and fully verified professionals 
2. Designed to help you: research design (e.g., questionnaire, interview guides) based on clients business objectives 
3. Easy takeaways: analysis & insights presentation with takeways and recommendations presented in a board room ready fashion
4. Quality: won many quality awards for best research vendor (e.g., Hedgeweek, Greenbooks)
5. Serving largest players: serving Big Tech (4/5 biggest players), market research, consulting (4 biggest players), F500 companies, PEs and Hedge Funds
    Your Company Mission: We’re on a mission to uncover world-class knowledge.
    
    Your Work History: 
History - Company Name: NewtonX, Title: Strategic Account Director, Start Date: ?, End Date: ?
History - Company Name: Oak Street Health, Title: Sales Director, Start Date: ?, End Date: ?
History - Company Name: Gartner, Title: Large Enterprise Account Executive, Start Date: ?, End Date: ?
History - Company Name: Revel Technology, Title: Account Executive, Start Date: ?, End Date: ?
History - Company Name: Kindred Healthcare, Title: Clinical Liaison, Start Date: ?, End Date: ?
History - Company Name: Good Shepherd Hospice, Title: Hospice Consultant, Start Date: ?, End Date: ?
History - Company Name: Healix, LLC, Title: Managed Care Specialist, Start Date: ?, End Date: ?
History - Company Name: Walgreens, Title: Pharmacy Technician, Start Date: ?, End Date: ?
      
      """.strip()

    return ""


def get_email_step_example(example_num: int, step_num: int):

    # Hristina Bell
    if example_num == 1:
        if step_num == 1:
            return f"""
        
## Assets: 
Title: Doppler Securing Insurance
Value: <p>Doppler offers advanced secrets management to secure financial and insurance platforms, enhancing transaction security and automating secret rotation. The platform provides comprehensive audit trails to track secret usage and streamline regulatory compliance in the insurance sectors. Features include role-based access control, encryption-at-rest and in-transit, and detailed access and change logs for operational transparency.</p>
Tag: Research

Title: $50 Gift Card
Value: We are offering a $50 Gift Card for potential clients to schedule a call with us. During the call, we aim to gather information about their devops system, understand their priorities, and explore potential collaboration opportunities.
Tag: Offer


## Output:
### Email:
Hi [[prospect first name]],

As a [[informalized prospect title. all lowercase]], you're responsible for keeping [[ informalized prospect company name]]'s systems secure and efficient. You probably haven't heard of us yet, but I'm reaching out from Doppler, a secrets management platform. I'd love to get us on your radar.

Our platform helps manage, orchestrate, and rotate secrets across any environment or app config, simplifying your tasks and boosting security. This is especially relevant if you're dealing with insurance data - which, from what I understand about [[informalized prospect company name]], you are.

If relevant, free for a quick 15-20 minute chat next week?

As a thank you, I'd love to send over a $50 Amazon gift card for your time.

Best,

Hristina
### Angle: Security-Focused with Incentive
        
        """.strip()

        if step_num == 2:
            return f"""
        
## Assets: 
Title: Integrations with AWS, Azure, GCP and More
Value: <p>Doppler seamlessly integrates with leading cloud providers such as AWS, Azure, and GCP, which is essential for insurance industries. These integrations enable secure management of secrets and compliance with high-security standards in the financial sector.</p>
Tag: Value Prop


## Output:
### Email:
Hi [[prospect first name]],

I'm guessing that you all already have a secrets management solution in place.

Do you all use AWS, Azure, GCP, and/or something else?

We seamlessly integrate with all these platforms. This allows for secure management of secrets and compliance with the high-security standards in the insurance sector.

Would you be open for a quick call on how we can save you hours per week on secrets management?

Have a nice Wednesday :)

Hristina
hbencheva@gmail.com
925.348.5239
### Angle: Security-Focused with Incentive
        
        """.strip()

        if step_num == 3:
            return f"""

## Assets: 
Title: Integrations with AWS, Azure, GCP and More
Value: <p>Doppler seamlessly integrates with leading cloud providers such as AWS, Azure, and GCP, which is essential for insurance industries. These integrations enable secure management of secrets and compliance with high-security standards in the financial sector.</p>
Tag: Value Prop


## Output:
### Email:
Hi [[prospect first name]] - haven't heard back.

Can you just let me know if you're:

1. not looking to change your secrets management solution

2. not interested

3. not the right contact

Best,
Hristina
### Angle: Security-Focused with Incentive
          
          """.strip()

    # Ishan Sharma
    if example_num == 2:
        if step_num == 1:
            return f"""
          
## Assets: 
Title: Followed by Top VCs
Value: DailyDropout.fyi has a strong following from top investors like Sequoia, Kleiner Perkins, Lightspeed, Contrary, and others. They have a wide readership of over 130k+ including venture capitalists, founders, and more.
Tag: Phrase

Title: We'd love to feature their startup!
Value: <p>Let the recipient know that we found their startup quite interesting and would love to feature them in our newsletter! Let them know that (1) this is free of cost (2) we'll handle writing, editing, sending, distributions, and (3) we accept donations if they're open to it.</p>
Tag: Offer


## Output:
### Email:
Happy Monday [[ first name ]]! 👋 I'm Ishan, the editor-in-chief here at DailyDropout.fyi. (startup newsletter with 130k+ subscribers, we feature interesting startups every week to get interesting companies in front of investors and future employees).

I recently came across [[ colloquialized prospect's company ]] and wanted to personally reach out - we were just thinking about making our next feature about a co. in the [[ 1-2 words phrase, casual lowercase space. Ensure it's only 1-2 words maximum. ]] space.

**The ask: would you like to be featured?**

Best,

Ishan


Answers to a couple common questions I get asked:

1. _How does this work?_ -> We'll handle writing, editing, and publishing! One ask we have for you is that you share on socials once published.

2. _How much does this cost?_ -> Entirely free for you! However, we do accept donations. Typically, startups have donated anywhere from $50 to $1,000 to support our platform in the past. Any amount helps - I can send a stripe link if you'd like to support.
### Angle: Exclusive Feature Invitation with Support Option
          
        """.strip()

        if step_num == 2:
            return f"""

## Assets: 
Title: Tranch Case Study
Value: <p>Tranch is a fintech startup that provides non-dilutive cash solutions for fast-growing businesses. We featured them in our newsletter a couple months back. After being featured - we got them 30k+ views, hundreds of link clicks, and many conversations.</p> https://dailydropout.substack.com/p/tranch-non-dilutive-cash-for-startups
Tag: Case Study


## Output:
### Email:
Just wanted to circle back here [[ first name ]].

A couple months back, we featured tranch (startup in the fintech space) and they had over 35,000+ impressions with hundreds of clicks towards their website within 48 hours of publishing.

Link: [Tranch - DailyDropout.fyi Article](https://dailydropout.substack.com/p/tranch-non-dilutive-cash-for-startups)

Let me know if you'd like to get [[ company name ]] featured as well! We'd love to get the word out there.

Ishan
### Angle: Security-Focused with Incentive
          
        """.strip()

        if step_num == 3:
            return ""

    # Shivang Patel
    if example_num == 3:
        if step_num == 1:
            return f"""
          
## Assets: 
Title: Article on HR in the Insurance Industry
Value: The insurance industry is facing a crisis due to an aging workforce and a knowledge shortfall among new professionals entering the field. This talent gap was highlighted during the 2017 hurricane season when the demand for adjusters far exceeded the supply. The lack of experienced professionals can lead to mistakes in claims handling, ethical concerns, and ultimately harm policyholders and insurers. https://www.businessinsurance.com/article/20240205/NEWS06/912362439/Perspectives-An-industry-in-crisis-%E2%80%94-challenges-and-opportunities
Tag: Research

Title: Talent strategy trends offer
Value: <p>NewtonX has helped several companies in creating a competitive talent strategy; we'd love to offer some top trends we're seeing in talent in the insurance space.</p>
Tag: Offer


## Output:
### Email:
Hi [[first name]],

[[Some variation of: I noticed that you're leading HR/people/etc. at informalized prospect company name]]. I trust you're aware of the crisis facing large insurers: an aging workforce, knowledge shortfall, and attrition. (Source: [Business Insurance](https://www.businessinsurance.com/article/20240205/NEWS06/912362439/Perspectives-An-industry-in-crisis-%E2%80%94-challenges-and-opportunities))

It can be tough to manage, but not impossible.

At NewtonX, we've been helping companies create competitive talent strategies. We'd love to share some top insurance talent trends we're seeing. Maybe it'd be valuable for your next exec meeting.

Would you be open to a brief call next week to discuss this further?

Best,
Shivang
### Angle: Addressing HR Challenges with Expertise Offer

        """.strip()

        if step_num == 2:
            return f"""
          
## Assets: 
Title: Case study: How a design software company uncovered trends and best practices for hiring designers with NewtonX
Value: <p><span style="color: rgb(0, 0, 0);">NewtonX surveyed 300 design hiring managers in four countries over 10 days for a design software firm, uncovering hiring trends and emphasizing supportive cultures, personalized recruitment, and development opportunities, against a backdrop of 23% job growth in digital design by 2031.</span></p><p><br></p><p>URL: https://eng7e.seismic.com/i/gQYIGwxf0nN9Y8HZzoHuJWA1mW___xw6___lPLUSSIGNp7lzPAitYg8Xqu8cPLUSSIGN8Ud6Tg9MgjefO6VGMdPAFrtLz6PLUSSIGNkCpkQozmQ___LnKv8x6wXqgC7WsBqn___XArcRK3ztvQix55jRpqGUZ</p><p><br></p>
Tag: Case Study

Title: Talent strategy trends offer
Value: <p>NewtonX has helped several companies in creating a competitive talent strategy; we'd love to offer some top trends we're seeing in talent in the insurance space.</p>
Tag: Offer


## Output:
### Email:          
Hi [[first name]],

I hope the previous article I shared got you thinking about the talent strategies at [[informalized prospect company name]]. To further illustrate the value we can bring, I'd like to share a case study where we helped a $bn company uncover hiring trends and best practices.

Here's the link: [Case Study](https://eng7e.seismic.com/i/gQYIGwxf0nN9Y8HZzoHuJWA1mW___xw6___lPLUSSIGNp7lzPAitYg8Xqu8cPLUSSIGN8Ud6Tg9MgjefO6VGMdPAFrtLz6PLUSSIGNkCpkQozmQ___LnKv8x6wXqgC7WsBqn___XArcRK3ztvQix55jRpqGUZ)

I'd like to offer you a comprehensive analysis of the HR Insurance landscape. This customized report will provide actionable insights to help [[company]] address unique HR needs and stay ahead of the competition.

Let me know if this sounds interesting and we can set up a time to delve into details.

Best,

Shiv
### Angle: Addressing HR Challenges with Expertise Offer

        """.strip()

    return None
