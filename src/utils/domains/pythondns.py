import dns.resolver


def spf_record_valid(domain: str) -> tuple[str, bool]:
    """Gets the SPF record for the domain and determines if it is valid

    Args:
        domain (str): The domain to check

    Returns:
        tuple[str, bool]: The SPF record and whether it is valid
    """
    # pass
    try:
        spf_answers = dns.resolver.resolve(domain, "TXT")
        for answer in spf_answers:
            spf_text = answer.to_text()
            spf_text = spf_text.strip('"')
            if spf_text.startswith("v=spf1"):
                # SPF record needs to match Google's SPF record exactly
                if (
                    spf_text != "v=spf1 include:_spf.google.com ~all"
                    and spf_text != "v=spf1 include:amazonses.com ~all"
                ):
                    return spf_text, False

                return spf_text, True
    except:
        return "", False

    return "", False


def dmarc_record_valid(domain: str) -> tuple[str, bool]:
    """Gets the DMARC record for the domain and determines if it is valid

    Args:
        domain (str): The domain to check

    Returns:
        tuple[str, bool]: The DMARC record and whether it is valid
    """
    # pass
    try:
        dmarc_answers = dns.resolver.resolve("_dmarc." + domain, "TXT")
        for answer in dmarc_answers:
            dmarc_record = answer.to_text()
            dmarc_record = dmarc_record.strip('"')

            # DMARC record rua tag should be set to the sellscale inbox at the domain
            if f"rua=mailto:sellscale@{domain}" not in dmarc_record:
                return dmarc_record, False

            return dmarc_record, True
    except:
        return "", False

    return "", False


def dkim_record_valid(domain: str) -> tuple[str, bool]:
    """Gets the DKIM record for the domain and determines if it is valid

    Args:
        domain (str): The domain to check

    Returns:
        tuple[str, bool]: The DKIM record and whether it is valid
    """
    from src.domains.services import get_aws_dkim_records

    # Check for Google DKIM record
    try:
        dkim_answers = dns.resolver.resolve("google._domainkey." + domain, "TXT")
        if dkim_answers:
            for answer in dkim_answers:
                dkim_record = answer.to_text()
                dkim_record = dkim_record.strip('"')

                # DKIM record should be at least 20 characters long
                if len(dkim_record) < 20:
                    return dkim_record, False

                return dkim_record, True
    except:
        pass

    try:
        # Check for AWS DKIM record
        dkim_record = get_aws_dkim_records(domain_name=domain)
        if dkim_record:
            return dkim_record, True
    except:
        pass

    return "", False
