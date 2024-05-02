from typing import Optional
from src.onboarding.onboarding_generation import get_summary_from_website
from model_import import Client
from src.ml.services import get_text_generation


def generate_client_assets(
    client_id: int,
    text_dump: str,
    website_url: Optional[str] = None,
    additional_prompting: Optional[str] = None,
    num_pain_points: Optional[int] = -1,
    num_value_props: Optional[int] = -1,
    num_social_proof: Optional[int] = -1,
    num_how_it_works: Optional[int] = -1,
):

    client: Client = Client.query.get(client_id)
    client_name = f"""Name: {client.company}""" if client.company else ""
    client_tagline = f"""Tagline: {client.tagline}""" if client.tagline else ""
    client_description = (
        f"""Description: {client.description}""" if client.description else ""
    )
    client_key_value_props = (
        f"""Key Value Props: {client.value_prop_key_points}"""
        if client.value_prop_key_points
        else ""
    )
    client_mission = f"""Mission: {client.mission}""" if client.mission else ""
    client_impressive_facts = (
        f"""Impressive Facts: {client.impressive_facts}"""
        if client.impressive_facts
        else ""
    )

    if website_url:
        website_summary = get_summary_from_website(website_url)
    else:
        website_summary = None
    website_summary = (
        f'''Website Summary: "{website_summary}"''' if website_summary else ""
    )

    pain_point_example = f"""
    
Title: High costs with collecting images
Value: Today, there is extensive time and high costs associated with collecting images for training computer vision models.
Tag: Pain Point

Title: Adaptability of mnfg lines
Value: Changes in the manufacturing line process means you have to rephrase a training process.
Tag: Pain Point
    
    """

    value_prop_example = f"""
    
Title: Breakthrough in Computer Vision Model Performance
Value: Advex enables computer vision engineers to deploy top-performing models within hours, drastically improving accuracy with as few as 5-10 real images for training, thanks to our generative AI technology.
Tag: Value Prop

Title: Streamlining Visual Inspection Processes
Value: Our solution not only reduces the cost and time of data collection but also adapts to changes post-deployment, preventing downtime and eliminating the need for repetitive data gathering.
Tag: Value Prop

Title: Precision in Manufacturing Through AI
Value: By leveraging generative AI, Advex can create synthetic data sets that lead to higher model accuracy for defect detection and quality control in manufacturing processes.
Tag: Value Prop
    
    """

    how_it_works_example = f"""
    
Title: Getting started
Value: Getting started with Ash is easy: 1. Order test kit 2. Test kit shipped in 24 hours 3. Customers self-collect at home 4. Customer ships to lab 5. Lab results in 3-5 days
Tag: How it Works

Title: Detect defection & segmentation
Value: Detect defection & segmentation → many boxes on a conveyor belt and the segmentation model will say where the box is
Tag: How it Works
    
    """

    social_proof_example = f"""
    
Title: Adaptability of mnfg lines
Value: Auto-manufacturer was previously experiencing 55% defect rates. After implementing, they saw a 52% reduction from using Advex's AI technology after 3 months.
Tag: Social Proof

Title: OpenAI Used Us
Value: We helped facilitate the vision models that OpenAI uses in Mission Bay, could help you with your vision models too.
Tag: Social Proof
    
    """

    prompt = f"""
    
You are working with a new client to create a series of marketing assets for them. These assets are unique value props, pain points, social proofs, unique facts, etc that can be used in marketing outreach.
You will be provided with some general information to give context about the client and then you will be provided a text dump.
Please use the text dump to create at least 3 value prop-based marketing assets, 3 pain point-based marketing assets, 2 social proof-based marketing assets, 2 unique fact-based marketing assets, and as many as possible phrase or template marketing assets.
If you're unable to meet that criteria, it's okay. Just do your best and prioritize concise quality assets over quantity.

{additional_prompting if additional_prompting else ""}

Here's a previous example of what you're expected to generate.
# Previous Example #

## Client Information:
Name: Advex AI
Tagline: Deliver Top Performing AI Vision in Hours
Description: Advex uses generative AI to create to eliminate long and expensive data collection cycles for creating computer vision models.
Website Summary: "Name: Advex\nDescription: Advex is a company focused on unlocking Computer Vision with Generative Synthetic Data. They recognize that collecting the right data to build computer vision models is a challenging and time-consuming task. Therefore, they use foundation models to automatically detect and synthesize the missing data.\nValue Props: \n- Unlocking Computer Vision with Generative Synthetic Data\n- Using foundation models to automatically detect and synthesize missing data\n- Time and cost efficiency in data collection for computer vision models\nMission Statement: Advex's mission is to revolutionize the field of computer vision by using generative synthetic data. They aim to alleviate the time and cost-intensive process of data collection by leveraging foundation models to detect and synthesize missing data automatically."

## Text Dump:
--------------------------------------------------------------------------

### First campaign

Who to target

Contact detail: 

- Machine vision
    - specific for manufacturing / apparel / semi-conductor / automative / medical / pharma / food packing / agricultural
        - battery, logistics, automative, food packing, pharma,
- computer vision
    - this is a lot more broad. ideally put manufacturing or manufacturing automation in their title.

Account detail:

- > 100 people at the company. >$25m in revenue.  “Manufacturing”

---

What to say

Pain points

- sup bar model performance have poor accuracy eg., “computer vision model to detect defects on manufacturing likes”.
    - sometimes can be finding a package or navigating a warehouse. robitcs.
- long or expensive data collection of images to train a computer vision model
    - a lot of time to set up the computer vision model. inspection, or finding the location of something. if model is not performing well.
- once deploying model, if things changes, you have to redo the data collection process and re-train the process. variability post-deployment or machine-downtime post deployment

- Successful saying:
    "We helped facilitate the vision models that OpenAI uses in Mission Bay, could help you with your vision models too."

What they have in place

- for very simple use cases, they likely have something simple and it works. They wonder if the thing solves the problem. For any other cases, they may have tried with other systems, but haven’t implemented. To get it to work, can take a long time

Value props

Advex helps comptuer vision engineers with delivering top performing computer models in hours. he can also send material. 

Leverage generative Ai to reduce costs

- faster time to value: 5-10 real images for synthetic images
- higher accuracy: improve quality of data sets by
- Reduce downtime: once we’re on the line, we can adopt to new products, defects, changes,

Social Proof

- Auto maker: We worked with an auto-maker
- social proof
    
    ![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/d3077c4b-8fa0-484c-bba1-dcd5e8f5ee41/9142e2cc-8ebc-44b1-b954-ad6fcf62bc1d/Untitled.png)
    
    ![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/d3077c4b-8fa0-484c-bba1-dcd5e8f5ee41/0a407177-e1cd-49de-87b4-f5bf978694da/Untitled.png)
    
They were experiencing 55% defect rates. With us they saw a 52% reduction in defects after 3 months.
    
- Robotics pick-n-place:
    
    ![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/d3077c4b-8fa0-484c-bba1-dcd5e8f5ee41/e266464e-35ec-427b-83bb-e3a792ca92bd/Untitled.png)
    
- 10k fake images out performed good image
    
    ![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/d3077c4b-8fa0-484c-bba1-dcd5e8f5ee41/faabd0c5-62e3-4d78-a9af-85d90ac882ff/Untitled.png)
    

how it works 1.

- 
- detect defection & segmentation → many boxes on a conveyor belt and the segmentation model will say where the box is

Data collection issues. Issue with variation and variety and high change-over in parts. 

How it works 2.
is that you first order test kit which is shipped in about in 24 hours.
Customers self-collect it at home and ship is to the lab. 
Should see results in three to five days-ish.


Call to action

- Discovery question:
    - are visual tasks importnt in your manufacturing process?
    - Do you automate visual inspections or other visual tasks?
    - Do you use [KEYENCE](https://www.keyence.com/)? Or Cognex but it was too complicated
- pain based:
    - have you ever been promised that a computer vision model only needs 5-10 images and found that once it’s deployed you need thousands or lots more?
    - Do you find defects are difficult to collect / difficult to train model on defective classes?
- Robotics:
    - Would it be beneficial to deploy on customer sites faster without data collection time?
    - have you looked at automation systems but decliend because of ROI

### Angle

They’ve had a lot higher success when attaching case studies to the sequence. 

There’s a suspicion that they have strong conversion if they can accurately target people who’ve tried cognix or keyence or failed to do a task. 

case study and link has been the best so far. no case study lower open rate.

### Format ==

1. Start with overview just gives a background
    1. more sophistacted, the more they think they need data.
2. then Go to case study (highest open rate)

--------------------------------------------------------------------------

# Output:

{num_value_props != -1 and value_prop_example or ""}

{num_pain_points != -1 and pain_point_example or ""}

{num_how_it_works != -1 and how_it_works_example or ""}

{num_social_proof != -1 and social_proof_example or ""}

## Client Information:
{client_name}
{client_tagline}
{client_description}
{client_key_value_props}
{client_mission}
{client_impressive_facts}
{website_summary}

## Text Dump:
--------------------------------------------------------------------------
{text_dump}
--------------------------------------------------------------------------

## Additional Requirements:
{((num_value_props or 0) + (num_pain_points or 0) + (num_how_it_works or 0) + (num_social_proof or 0)) > 0 and "It is important that you generate ONLY the required number of assets based on the following criteria:" or ""}
{num_value_props != -1 and num_value_props and f"- Create {num_value_props} Value Props" or ""}
{num_pain_points != -1 and num_pain_points and f"- Create {num_pain_points} Pain Points" or ""}
{num_how_it_works != -1 and num_how_it_works and f"- Create {num_how_it_works} How It Works" or ""}
{num_social_proof != -1 and num_social_proof and f"- Create {num_social_proof} Social Proofs" or ""}
{((num_value_props or 0) + (num_pain_points or 0) + (num_how_it_works or 0) + (num_social_proof or 0)) > 0 and "DO NOT create more than the required number of assets." or "Generate 5-10 assets with a mix of value props, pain points, social proofs, unique facts, phrases, and templates."}

# Your Turn 
Okay now it's your turn to generate some assets for the client. Remember to prioritize quality over quantity.

IMPORTANT: ONLY generate the assets, do not include any other information in your response.

# Output:
    
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
            model="gpt-4-turbo-preview",
            max_tokens=4000,
            type="CLIENT_ASSETS",
            use_cache=True,
        )
        or ""
    )

    return parse_data_to_assets(completion)


def parse_data_to_assets(data: str):
    assets = []
    # Split the data into sections based on double newline, filtering out empty strings
    sections = [section for section in data.split("\n\n") if section]

    for section in sections:
        try:
            # Split each section into lines and remove empty lines
            lines = [line for line in section.split("\n") if line]
            # Extract title, value, and tags from lines assuming consistent ordering
            title = lines[0].replace("Title: ", "").strip()
            value = lines[1].replace("Value: ", "").strip()
            tag = lines[2].replace("Tag: ", "").strip()
            # Append the extracted data as a dict to the assets list
            assets.append(
                {
                    "title": title.replace("**", "")
                    .replace("Title:", "")
                    .replace("#", "")
                    .strip(),
                    "value": clean_value(value),
                    "tag": convert_tag_to_asset_tag(tag),
                }
            )
        except:
            pass

    return assets


def clean_value(value: str):
    # Remove leading header
    value = value.replace("**", "").replace("Value:", "").strip()
    return value


def convert_tag_to_asset_tag(tag: str):
    original_tag = tag
    tag = tag.lower().strip()

    if "value" in tag:
        return "Value Prop"
    elif "pain" in tag:
        return "Pain Point"
    elif "social" in tag:
        return "Social Proof"
    elif "fact" in tag:
        return "Value Prop"
    elif "phrase" in tag:
        return "Phrase"
    elif "offer" in tag:
        return "Offer"
    elif "research" in tag:
        return "Research"
    elif "quote" in tag:
        return "Quote"
    elif "cta" in tag:
        return "LinkedIn CTA"
    elif "linkedin template" in tag:
        return "LinkedIn Template"
    elif "email template" in tag:
        return "Email Template"
    else:
        return original_tag.replace("**", "").replace("#", "").replace("Tag:", "").strip()
