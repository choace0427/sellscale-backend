import sys
import time
import random


def print_loading_animation(duration):
    """Prints 'loading...' animation for a given duration."""
    end_time = time.time() + duration
    while time.time() < end_time:
        for dot_count in range(4):  # Cycle through 0 to 3 dots
            sys.stdout.write(
                "\rAI: loading" + "." * dot_count
            )  # Overwrite the current line
            sys.stdout.flush()
            time.sleep(0.5)  # Adjust for speed of animation
            if time.time() >= end_time:
                break
    sys.stdout.write("\r\033[K")  # Clear the line
    sys.stdout.flush()


def print_response_slowly(response):
    """Prints the response one character at a time to simulate typing."""
    for char in response:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(
            random.uniform(0.005, 0.03)
        )  # Randomize the delay for a more natural feel


def print_cool_intro():
    print("⚡️ Created thread: st-A2893NIKUxxOIqmsiENM-8391\n")
    messages = [
        "🔍 ... loading Search Engine API (SERP v.1.0.2)",
        "💾 ... loading SellScale Prospect Database (cnt. 301,381,173)",
        "🚀 ... loading Vectorized Asset Engine",
        "🧠 ... loading SegmentGPT API",
        "📈 ... loading SalesSequence LLM (v.4.0.3)",
        "📊 ... ingesting historical company analytics for NewtonX",
        "🏢 ... ingesting historical company information for NewtonX",
        "👤 ... ingesting rep information: Ishan Sharma",
    ]
    print("LOADING SELLSCALE DEPENDENCIES: ")
    max_length = max(len(message) for message in messages) + 6  # Increased padding
    print("#" * max_length)
    for message in messages:
        print("#", end=" ")
        print_response_slowly(message + " " * (max_length - len(message) - 4) + "#\n")
        time.sleep(0.5)  # Brief pause before the next line starts
    print("#" * max_length)
    time.sleep(2)  # Simulate loading time after the block is printed

    print("\n\n-------------------\nConversation:\n\n")


def fake_ai_conversation():
    responses = [
        (
            "🤖 AI: Hello Ishan! I'm SellScale AI. To kick things off, what kind of campaign did you want to run today?",
            True,
        ),
        (
            """
🤖 AI: Great. Here's a couple names you can choose between, which one do you prefer?
a. 'New York Hedge Fund Managers'
b. 'Directors + VPs at NYC Hedge Funds'
c. 'Hedge Fund Decision Makers'
         """,
            True,
        ),
        (
            """
[⚡️ ACTION: create_campaign('Directors + VPs at NYC Hedge Funds')]
""",
            False,
        ),
        (
            """
🤖 AI: Great - the campaign has been successfully created! Here's what I'll do to create your prospect list.
1. I am going to look for the top 30 hedge funds in New York
2. I will then look for decision makers like directors and managers.
3. I will then proceed to process the list and verify it's accurate.

Give me a moment.
        """,
            False,
        ),
        (
            """
[⚡️ ACTION: search("top 30 hedge funds in New York")]
""",
            False,
        ),
        (
            """
🤖 AI: I found the top 30 Hedge Funds in New York! Here are the first few:
- Renaissance Technologies - www.rt.com
- Citadel - www.citadel.com
- Elliot Management - www.elliot.io
- Bridgewater - www.bw.com

I'm going to look for decision makers (directors and managers) at these hedge funds now.
        """,
            False,
        ),
        (
            """
[⚡️ ACTION: find_contacts("managing partners, directors", list_30_hedge_funds)
""",
            False,
        ),
        (
            """
🤖 AI: I found 1,391 directors and VPs at hedge funds in New York. Here's a sample:
- 👥 Rebecca Jordan, Director [linkedin.com/rebeccajordan]
- 👥 Fernance Morin, Managing Partner [linkedin.com/fernancemorin]
- 👥 Monica Patel, Vice President [linkedin.com/monicapatel]

How do these contacts look? Anything you'd like to adjust?
""",
            True,
        ),
        (
            """
🤖 AI: On it! Sounds like you want to target vice presidents only. Let me adjust your filtering now
""",
            False,
        ),
        (
            """
[⚡️ ACTION: find_contacts("vice presidents", list_30_hedge_funds)
""",
            False,
        ),
        (
            """
🤖 AI: I found 731 vice presidents at hedge funds in New York. I've listed a couple examples list below:
- 👥 Monica Patel, Vice President [linkedin.com/monicapatel]
- 👥 Stewart M. Johnson, Vice President [linkedin.com/stewartmjohnson]
- 👥 Johnathan Smith, Vice President [linkedin.com/johnathansmith]

By the way Ishan, I noticed that you went to Stanford in 2015. Would you like me to filter this list to only include contacts that went to Stanford University?
""",
            True,
        ),
        (
            """
🤖 AI: Go trees! Targetting contacts that went to your university is a great strategy. 
I will adjust the filtering to only include contacts that went to Stanford University while looking for vice presidents at hedge funds in New York.
""",
            False,
        ),
        (
            """
[⚡️ ACTION: find_contacts("vice presidents", list_30_hedge_funds, "Stanford University")
""",
            False,
        ),
        (
            """
🤖 AI: I found the following 27 vice presidents at hedge funds in New York who went to Stanford University. Review three below:
- 👥 Monica Patel, Vice President [linkedin.com/monicapatel] (Stanford University)
- 👥 Joshua P. Quin, Vice President [linkedin.com/joshuapquin] (Stanford University)
- 👥 Colin Z. Plath, Vice President [linkedin.com/colinzplath] (Stanford University)

How do these contacts look? Anything you'd like to adjust?
""",
            True,
        ),
        (
            """
🤖 AI: Great! I will now proceed to process the list and verify it's accurate 
""",
            False,
        ),
        (
            """
[⚡️ ACTION: score_contacts(list_27_vp_hedge_funds)
""",
            False,
        ),
        (
            """
🤖 AI: I've gone ahead and imported, reviewed, and scored the profiles of all 27 contacts in this campaign.
🟩 23 Very High Fits
🟦 4 High Fits
🟨 0 Medium Fits
🟧 0 Low Fits
🟥 0 Very Low Fits

Let's get started with writing the campaign sequence. To kick things off, let me check your asset library for any interesting assets.
""",
            False,
        ),
        (
            """
[⚡️ ACTION: find_relevant_assets("hedge funds", "vice presidents")
""",
            False,
        ),
        (
            """
🤖 AI: I found two interesting assets in the NewtonX library that you may want to use in this campaign:
1. Coffee chat: This is a low cost, casual offer to connect with a prospect over a coffee chat.
[conversion: 32%; past users: Morgan P., Johnathan S.]

2. NYC NewtonX Conference: This is a high cost, high value offer to connect with a prospect at a conference in NYC.
[conversion: 78%; past users: Rebecca J.]

Would you like to use any of these assets in your campaign?
""",
            True,
        ),
        (
            """
🤖 AI: Are there any other assets you'd like for us to use?
""",
            True,
        ),
        (
            """
🤖 AI: Inviting them to get lunch at the office is a great idea! I will create that asset and connect it to your campaign.
""",
            False,
        ),
        (
            """
[⚡️ ACTION: create_asset("Lunch @ NewtonX Office", "Invite your prospect to get lunch at the NewtonX office")
""",
            False,
        ),
        (
            """
🤖 AI: I've created the asset and connected it to your campaign. Let's move on to the next step which is writing the copy.

I will proceed to create a 3 step LinkedIn sequence for this campaign.
""",
            False,
        ),
        (
            """
[⚡️ ACTION: create_sequence("LinkedIn", "3-step", "hedge funds", "vice presidents", assets=["Coffee chat", "Lunch @ NewtonX Office", "NYC NewtonX Conference"])
""",
            False,
        ),
        (
            """
🤖 AI: I've created the sequence and connected it to your campaign. Here's a preview of three steps:

Step 1: Coffee chat
"Hi [First Name], fellow Stanford-alum reaching out - would love to connect over a coffee chat and learn more about your work at [Hedge Fund Name]. I've been meaning to connect with more finance leaders in the area"

Step 2: Lunch @ NewtonX Office
"Hi [First Name], I'm hosting a lunch at the NewtonX office next week and would love to invite you. I think you'd find the conversation with our team and other finance leaders valuable"

Step 3: NYC NewtonX Conference
"Hi [First Name], I'm inviting you to the NYC NewtonX conference next month. I think you'd find the conversations with other finance leaders valuable"

How does that look, Ishan?
""",
            True,
        ),
        (
            """
🤖 AI: Great! I will now proceed to create a review card for this campaign
""",
            False,
        ),
        (
            """
[⚡️ ACTION: create_review_card(campaign_id)
""",
            False,
        ),
        (
            """
🤖 AI: The review card has been successfully created. You can verify and make any final adjustments at this link:
https://app.sellscale.com/campaigns/8391/review

Best of luck with your campaign, Ishan! Let me know if you need anything else.
""",
            False,
        ),
    ]

    print_cool_intro()  # Print the cool intro block

    for response, wait_for_input in responses:
        random_timeout = random.randint(
            1, 2
        )  # Generate a random timeout between 1 to 3 seconds
        print_loading_animation(random_timeout)  # Print loading animation
        print("\n----\n")
        print_response_slowly(response)  # Simulate typing out the response
        if wait_for_input:
            user_input = input("\n✍🏼 You: ")
            if user_input.lower() == "goodbye":
                print_response_slowly("AI: Goodbye, Ishan!")
                break
        else:
            # Optionally, you can add another random delay or immediate continuation
            time.sleep(random.randint(1, 2))

    print_response_slowly("\nAI: That's all I have for now. Goodbye, Ishan!")


if __name__ == "__main__":
    fake_ai_conversation()
