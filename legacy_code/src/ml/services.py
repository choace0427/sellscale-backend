def get_sequence_draft(
    value_props: list[str], client_sdr_id: int, archetype_id: int
) -> list[dict]:
    """Generates a sequence draft for a client.

    Args:
        value_props (List[str]): The value props to use in the sequence.
        client_sdr_id (int): The client SDR id.

    Returns:
        List[str]: The sequence draft.
    """
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    client: Client = Client.query.get(client_sdr.client_id)
    personalization_field_name = client.vessel_personalization_field_name

    # Prompt Engineering - Value Proposition
    prompt = f"Value Proposition:\n"
    for i, v in enumerate(value_props):
        prompt += f"{i+1}. {v}\n"

    # Prompt Engineering - Persona
    prompt += f"\nPersona:\n"
    prompt += f"- Name: {archetype.archetype}\n"
    prompt += f"- Description: {archetype.icp_matching_prompt}\n"
    prompt += f"- Fit Reason: {archetype.persona_fit_reason}\n"

    # Prompt Engineering - SDR
    prompt += f"\nSales Person:\n"
    prompt += f"- Name: {client_sdr.name}\n"

    # Prompt Engineering - Instructions
    prompt += f"\nInstructions:\n"
    prompt += (
        f"- Write a sequence of emails that targets the value props and persona.\n"
    )
    prompt += f"- The emails need to address the recipient using {{{{first_name}}}} as a placeholder for the first name.\n"
    prompt += f"- The emails need to build off of each other.\n"
    prompt += f"- The second email should open with a question.\n"
    prompt += f"- The third email should reference results or a case study.\n"
    prompt += f"- Limit the sequence to 3 emails.\n"
    prompt += f"- In only the first email, you must include {{{{{personalization_field_name}}}}} after the salutation but before the introduction and body.\n"
    prompt += f"- Do not include other custom fields in the completion.\n"
    prompt += f"- Sign the email using 'Best' and the Sales Person's name.\n"
    prompt += f"Example sequence:\n"
    prompt += f"subject: 80% of US Physicians are on Doximity\n"
    prompt += f"Hey {{First_Name}},"
    prompt += f"As Doximity’s official physician staffing firm, we use our exclusive access to 80% of U.S. physicians on Doximity and our sophisticated technology to intelligently source candidates so organizations like {{account_name_or_company}} can land their next physician hire faster and more cost-effectively."
    prompt += f"I’d love to chat for 15 minutes about how Curative can help fill your most challenging roles –⁠ when are you free to chat?"
    prompt += f"Thanks,"
    prompt += f"{{Your_Name}}"
    prompt += f"\n\n--\n\n"
    prompt += f"subject: Speciality market analysis report\n"
    prompt += f"Hey {{First_Name}},"
    prompt += f"Our exclusive access to Doximity allows us to have the deepest pool of active and passive candidates in the industry, using comprehensive data to identify where passive and active job seekers are for your search."
    prompt += f"I’d love to chat for 15 minutes about how Curative can help fill your most challenging roles –⁠ can you let me know what time works best for you?"
    prompt += f"Thanks,"
    prompt += f"{{Your_Name}}\n"
    prompt += f"\n\n--\n\n"
    prompt += f"subject: Sample of active/passive FM job seekers\n"
    prompt += f"Hey {{First_Name}},"
    prompt += f"Curative has access to a dynamic network of physicians that’s growing and being refreshed daily, allowing us to present new candidates not found on typical job boards."
    prompt += f"I’d love to set time aside to share the data we’re finding for physician placements at your org –⁠ when are you free to chat for 10 minutes? Would love to find a time!"
    prompt += f"Thanks,"
    prompt += f"{{Your_Name}}\n\n"

    # Prompt Engineering - Finish
    prompt += f"\nSequence:"

    # Generate Completion
    emails = wrapped_create_completion(
        # TODO: Use CURRENT_OPENAI_LATEST_GPT_MODEL when we gain access.
        model=OPENAI_CHAT_GPT_3_5_TURBO_MODEL,
        prompt=prompt,
        temperature=0.7,
        frequency_penalty=1.15,
        max_tokens=600,
    )
    if not emails:
        return False

    # Parse Completion
    parsed_emails = []

    i = 0
    for email in re.split(r"\s+subject: ", emails, flags=re.IGNORECASE | re.MULTILINE):
        parts = email.strip().split("\n", 1)
        if len(parts) != 2:
            continue

        subject = re.sub(r"^subject: ", "", parts[0].strip(), flags=re.IGNORECASE)

        body = re.sub(r"--\s?$", "", parts[1].strip(), flags=re.IGNORECASE)
        body = re.sub(r"-\s?$", "", body, flags=re.IGNORECASE)
        if i == 0:
            body = re.sub(
                r"^(.+){{.+}},",
                lambda m: f"{m.group(1)}{{First_Name}},\n\n{{SellScale_Personalization}}",
                body,
            )

        parsed_emails.append(
            {
                "subject_line": subject.strip(),
                "email": body.strip(),
            }
        )
        i += 1

    return parsed_emails
