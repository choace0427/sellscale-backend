from app import (
    aws_route53domains_client,
    aws_route53_client,
    aws_sesv2_client,
    aws_ses_client,
    aws_workmail_client,
)
from botocore.exceptions import ClientError
from src.utils.domains.pythondns import (
    dkim_record_valid,
    dmarc_record_valid,
    spf_record_valid,
)
import os


def register_aws_domain(domain_name: str):
    try:
        response = aws_route53domains_client.register_domain(
            DomainName=domain_name,
            IdnLangCode="",
            DurationInYears=1,
            AutoRenew=True,
            AdminContact={
                "FirstName": "Aakash",
                "LastName": "Adesara",
                "ContactType": "COMPANY",
                "OrganizationName": "SellScale",
                "AddressLine1": "12730 Lantana Ave",
                "City": "Saratoga",
                "State": "CA",
                "CountryCode": "US",
                "ZipCode": "95070",
                "PhoneNumber": "+1.4088380914",
                "Email": "engineering@sellscale.com",
                "ExtraParams": [],
            },
            RegistrantContact={
                "FirstName": "Aakash",
                "LastName": "Adesara",
                "ContactType": "COMPANY",
                "OrganizationName": "SellScale",
                "AddressLine1": "12730 Lantana Ave",
                "City": "Saratoga",
                "State": "CA",
                "CountryCode": "US",
                "ZipCode": "95070",
                "PhoneNumber": "+1.4088380914",
                "Email": "engineering@sellscale.com",
                "ExtraParams": [],
            },
            TechContact={
                "FirstName": "Aakash",
                "LastName": "Adesara",
                "ContactType": "COMPANY",
                "OrganizationName": "SellScale",
                "AddressLine1": "12730 Lantana Ave",
                "City": "Saratoga",
                "State": "CA",
                "CountryCode": "US",
                "ZipCode": "95070",
                "PhoneNumber": "+1.4088380914",
                "Email": "engineering@sellscale.com",
                "ExtraParams": [],
            },
            PrivacyProtectAdminContact=True,
            PrivacyProtectRegistrantContact=True,
            PrivacyProtectTechContact=True,
        )
        return (
            response.get("ResponseMetadata", {}).get("HTTPStatusCode", 500),
            response,
            "",
        )
    except ClientError as e:
        return 500, None, str(e)


def check_aws_domain_availability(domain_name: str):
    try:
        response = aws_route53domains_client.check_domain_availability(
            DomainName=domain_name, IdnLangCode=""
        )
        return (
            response.get("Availability", "UNAVAILABLE") == "AVAILABLE",
            response,
            "",
        )
    except ClientError as e:
        return False, None, str(e)


def get_tld_prices(tld: str):
    try:
        response = aws_route53domains_client.list_prices(
            Tld=tld,
        )
        return (
            response.get("Prices", [{}])[0]
            .get("RegistrationPrice", {})
            .get("Price", -1.0),
            response,
            "",
        )
    except ClientError as e:
        return -1.0, None, str(e)


def find_domain(domain_name: str):
    is_available, _, _ = check_aws_domain_availability(domain_name)
    if is_available:
        price, _, _ = get_tld_prices(domain_name.split(".")[-1])
        return True, {
            "domain_name": domain_name,
            "price": price,
        }
    else:
        return False, {}


def find_similar_domains(key_title: str, current_tld: str):
    prefixes = ["", "try", "get", "with", "use"]
    tlds = list(set([current_tld, "com", "net", "org"]))

    tld_prices = {}
    for tld in tlds:
        price, _, _ = get_tld_prices(tld)
        tld_prices[tld] = price

    similar_domains = []
    for prefix in prefixes:
        for tld in tlds:
            domain_name = f"{prefix}{key_title}.{tld}"
            is_available, _, _ = check_aws_domain_availability(domain_name)
            if is_available:
                similar_domains.append(
                    {
                        "domain_name": domain_name,
                        "price": tld_prices[tld],
                    }
                )

    return similar_domains


<<<<<<< HEAD
def generate_dkim_tokens(domain_name: str):
    # Generate DKIM tokens for the domain
    try:
        response = aws_sesv2_client.delete_email_identity(EmailIdentity=domain_name)
    except:
        pass
    response = aws_sesv2_client.create_email_identity(
        EmailIdentity=domain_name,
        DkimSigningAttributes={"NextSigningKeyLength": "RSA_2048_BIT"},
    )
    return response.get("DkimAttributes", {}).get("Tokens", [])


def get_hosted_zone_id(domain_name: str):
    """
    Get the hosted zone ID for a given domain name.

    :param domain_name: The domain name to search for
    :return: The hosted zone ID if found, else None
    """
    paginator = aws_route53_client.get_paginator("list_hosted_zones")

    for page in paginator.paginate():
        for zone in page["HostedZones"]:
            if zone["Name"] == domain_name.rstrip(".") + ".":
                return zone["Id"].split("/")[-1]

    return None


def add_email_dns_records(domain_name: str):
    hosted_zone_id = get_hosted_zone_id(domain_name)
    if hosted_zone_id is None:
        return False, "Hosted zone not found for domain"
    dkim_tokens = generate_dkim_tokens(domain_name)

    # DKIM records
    dkim_records = []
    for token in dkim_tokens:
        dkim_record = {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "{}._domainkey.{}".format(token, domain_name),
                "Type": "CNAME",
                "TTL": 300,
                "ResourceRecords": [{"Value": "{}.dkim.amazonses.com".format(token)}],
            },
        }
        dkim_records.append(dkim_record)

    # DMARC record
    dmarc_record = {
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": "_dmarc." + domain_name,
            "Type": "TXT",
            "TTL": 300,
            "ResourceRecords": [
                {
                    "Value": f'"v=DMARC1; p=none; rua=mailto:engineering@{domain_name}; ruf=mailto:engineering@{domain_name}"'
                }
            ],
        },
    }

    # SPF record
    spf_record = {
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": domain_name,
            "Type": "TXT",
            "TTL": 300,
            "ResourceRecords": [
                {"Value": '"v=spf1 include:amazonses.com include:_spf.google.com ~all"'}
            ],
        },
    }

    # Update DNS records
    aws_route53_client.change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={
            "Changes": dkim_records
            + [
                dmarc_record,
                spf_record,
            ]
        },
    )

    return (
        True,
        "DNS records added successfully",
    )


def is_valid_email_dns_records(domain_name: str):
    spf_record, spf_valid = spf_record_valid(domain=domain_name)
    dmarc_record, dmarc_valid = dmarc_record_valid(domain=domain_name)
    dkim_record, dkim_valid = dkim_record_valid(domain=domain_name)

    return {
        "spf_valid": spf_valid,
        "dmarc_valid": dmarc_valid,
        "dkim_valid": dkim_valid,
    }


def create_workmail_inbox(domain_name: str, user_name: str, password: str):
    organization_id = os.environ.get("AWS_WORKMAIL_ORG_ID")
    hosted_zone_id = get_hosted_zone_id(domain_name)
    if hosted_zone_id is None:
        return False, "Hosted zone not found for domain"

    # Associate the domain with the organization
    try:
        response = aws_workmail_client.register_mail_domain(
            OrganizationId=organization_id,
            DomainName=domain_name,
        )
    except:
        pass

    # Create a user and mailbox
    user = aws_workmail_client.create_user(
        OrganizationId=organization_id,
        Name=user_name,
        DisplayName=user_name,
        Password=password,
    )

    # Assign an email address to the user
    user_id = user["UserId"]
    aws_workmail_client.register_to_work_mail(
        OrganizationId=organization_id,
        EntityId=user_id,
        Email=f"{user_name}@{domain_name}",
    )

    return True, "Workmail inbox created successfully"
=======
def domain_blacklist_check(domain):
    import dns.resolver

    blacklists = [
        "0spamurl.fusionzero.com",
        "uribl.abuse.ro",
        "bsb.spamlookup.net",
        "black.dnsbl.brukalai.lt",
        "light.dnsbl.brukalai.lt",
        "bl.fmb.la",
        "communicado.fmb.la",
        "nsbl.fmb.la",
        "short.fmb.la",
        "black.junkemailfilter.com",
        "nuribl.mailcleaner.net",
        "uribl.mailcleaner.net",
        "dbl.nordspam.com",
        "ubl.nszones.com",
        "uribl.pofon.foobar.hu",
        "rhsbl.rbl.polspam.pl",
        "rhsbl-h.rbl.polspam.pl",
        "mailsl.dnsbl.rjek.com",
        "urlsl.dnsbl.rjek.com",
        "uribl.rspamd.com",
        "rhsbl.rymsho.ru",
        "public.sarbl.org",
        "rhsbl.scientificspam.net",
        "nomail.rhsbl.sorbs.net",
        "badconf.rhsbl.sorbs.net",
        "rhsbl.sorbs.net",
        "fresh.spameatingmonkey.net",
        "fresh10.spameatingmonkey.net",
        "fresh15.spameatingmonkey.net",
        "fresh30.spameatingmonkey.net",
        "freshzero.spameatingmonkey.net",
        "uribl.spameatingmonkey.net",
        "urired.spameatingmonkey.net",
        "dbl.spamhaus.org",
        "dnsbl.spfbl.net",
        "dbl.suomispam.net",
        "multi.surbl.org",
        "uribl.swinog.ch",
        "dob.sibl.support-intelligence.net",
        "black.uribl.com",
        "grey.uribl.com",
        "multi.uribl.com",
        "red.uribl.com",
        "uri.blacklist.woody.ch",
        "rhsbl.zapbl.net",
        "d.bl.zenrbl.pl",
    ]

    combinedlists = [
        "sa.fmb.la",
        "hostkarma.junkemailfilter.com",
        "nobl.junkemailfilter.com",
        "reputation-domain.rbl.scrolloutf1.com",
        "reputation-ns.rbl.scrolloutf1.com",
        "score.spfbl.net",
    ]

    whitelists = [
        "white.dnsbl.brukalai.lt",  # Brukalai.lt DNSBL white
        "dwl.dnswl.org",  # DNSWL.org Domain Whitelist
        "iddb.isipp.com",  # ISIPP Accreditation Database (IDDB)
        "_vouch.dwl.spamhaus.org",  # Spamhaus DWL Domain Whitelist
        "dnswl.spfbl.net",  # SPFBL.net Whitelist
        "white.uribl.com",  # URIBL white
    ]

    informationallists = [
        "abuse.spfbl.net",
    ]

    results = {
        "blacklists": [],
        "combinedlists": [],
        "whitelists": [],
        "informationallists": [],
    }

    for bl in blacklists:
        try:
            query = ".".join(reversed(str(domain).split("."))) + "." + bl
            answers = dns.resolver.resolve(query, "A")
            for rdata in answers:
                if rdata.address:
                    print(f"BL: {domain} is listed on {bl}")
                    results.get("blacklists").append(
                        {
                            "domain": domain,
                            "list_type": "blacklist",
                            "list_name": bl,
                            "status": "listed",
                        }
                    )
        except dns.resolver.NXDOMAIN:
            print(f"BL: {domain} is not listed on {bl}")
            results.get("blacklists").append(
                {
                    "domain": domain,
                    "list_type": "blacklist",
                    "list_name": bl,
                    "status": "not_listed",
                }
            )
            pass  # Not listed on this blacklist
        except dns.resolver.NoAnswer:
            print(f"BL: No answer from {bl}")
            results.get("blacklists").append(
                {
                    "domain": domain,
                    "list_type": "blacklist",
                    "list_name": bl,
                    "status": "no_answer",
                }
            )
            pass  # No answer received
        except dns.resolver.Timeout:
            print(f"BL: Timeout querying {bl}")
            results.get("blacklists").append(
                {
                    "domain": domain,
                    "list_type": "blacklist",
                    "list_name": bl,
                    "status": "timeout",
                }
            )

    for cl in combinedlists:
        try:
            query = ".".join(reversed(str(domain).split("."))) + "." + cl
            answers = dns.resolver.resolve(query, "A")
            for rdata in answers:
                if rdata.address:
                    print(f"CL: {domain} is listed on {cl}")
                    results.get("combinedlists").append(
                        {
                            "domain": domain,
                            "list_type": "combinedlist",
                            "list_name": cl,
                            "status": "listed",
                        }
                    )
        except dns.resolver.NXDOMAIN:
            print(f"CL: {domain} is not listed on {cl}")
            results.get("combinedlists").append(
                {
                    "domain": domain,
                    "list_type": "combinedlist",
                    "list_name": cl,
                    "status": "not_listed",
                }
            )
            pass
        except dns.resolver.NoAnswer:
            print(f"CL: No answer from {cl}")
            results.get("combinedlists").append(
                {
                    "domain": domain,
                    "list_type": "combinedlist",
                    "list_name": cl,
                    "status": "no_answer",
                }
            )
            pass
        except dns.resolver.Timeout:
            print(f"CL: Timeout querying {cl}")
            results.get("combinedlists").append(
                {
                    "domain": domain,
                    "list_type": "combinedlist",
                    "list_name": cl,
                    "status": "timeout",
                }
            )

    for wl in whitelists:
        try:
            query = ".".join(reversed(str(domain).split("."))) + "." + wl
            answers = dns.resolver.resolve(query, "A")
            for rdata in answers:
                if rdata.address:
                    print(f"WL: {domain} is listed on {wl}")
                    results.get("whitelists").append(
                        {
                            "domain": domain,
                            "list_type": "whitelist",
                            "list_name": wl,
                            "status": "listed",
                        }
                    )
        except dns.resolver.NXDOMAIN:
            print(f"WL: {domain} is not listed on {wl}")
            results.get("whitelists").append(
                {
                    "domain": domain,
                    "list_type": "whitelist",
                    "list_name": wl,
                    "status": "not_listed",
                }
            )
            pass
        except dns.resolver.NoAnswer:
            print(f"WL: No answer from {wl}")
            results.get("whitelists").append(
                {
                    "domain": domain,
                    "list_type": "whitelist",
                    "list_name": wl,
                    "status": "no_answer",
                }
            )
            pass
        except dns.resolver.Timeout:
            print(f"WL: Timeout querying {wl}")
            results.get("whitelists").append(
                {
                    "domain": domain,
                    "list_type": "whitelist",
                    "list_name": wl,
                    "status": "timeout",
                }
            )

    for il in informationallists:
        try:
            query = ".".join(reversed(str(domain).split("."))) + "." + il
            answers = dns.resolver.resolve(query, "A")
            for rdata in answers:
                if rdata.address:
                    print(f"IL: {domain} is listed on {il}")
                    results.get("informationallists").append(
                        {
                            "domain": domain,
                            "list_type": "informationallist",
                            "list_name": il,
                            "status": "listed",
                        }
                    )
        except dns.resolver.NXDOMAIN:
            print(f"IL: {domain} is not listed on {il}")
            results.get("informationallists").append(
                {
                    "domain": domain,
                    "list_type": "informationallist",
                    "list_name": il,
                    "status": "not_listed",
                }
            )
            pass
        except dns.resolver.NoAnswer:
            print(f"IL: No answer from {il}")
            results.get("informationallists").append(
                {
                    "domain": domain,
                    "list_type": "informationallist",
                    "list_name": il,
                    "status": "no_answer",
                }
            )
            pass
        except dns.resolver.Timeout:
            print(f"IL: Timeout querying {il}")
            results.get("informationallists").append(
                {
                    "domain": domain,
                    "list_type": "informationallist",
                    "list_name": il,
                    "status": "timeout",
                }
            )

    return results
>>>>>>> 8acb85294d6e595f9eea0fe05a6b9f978b9def83
