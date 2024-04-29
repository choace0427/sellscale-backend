from datetime import datetime, timedelta
import random
import string
from typing import Optional
import requests
import concurrent.futures
from app import (
    aws_route53domains_client,
    aws_route53_client,
    aws_ses_client,
    aws_workmail_client,
    aws_amplify_client,
)
from app import db, celery
from botocore.exceptions import ClientError
from src.aws.amplify import (
    create_aws_amplify_app,
    create_aws_amplify_branch,
    create_aws_amplify_domain_association,
)
from src.client.models import Client, ClientSDR
from src.client.sdr.email.models import EmailType, SDREmailBank
from src.client.sdr.email.services_email_bank import (
    create_sdr_email_bank,
    get_sdr_email_bank,
    sync_email_bank_statistics_for_sdr,
)
from src.domains.models import Domain
from src.slack.models import SlackNotificationType
from src.slack.slack_notification_center import (
    create_and_send_slack_notification_class_message,
)
from src.utils.converters.string_converters import (
    get_first_name_from_full_name,
    get_last_name_from_full_name,
)
from src.utils.domains.pythondns import (
    dkim_record_valid,
    dmarc_record_valid,
    spf_record_valid,
)
from src.smartlead.services import sync_workmail_to_smartlead
import os
import time
from src.utils.slack import send_slack_message, URL_MAP
from sqlalchemy import func
from src.slack.notifications.email_new_inbox_created import (
    EmailNewInboxCreatedNotification,
)


MAX_INBOXES_PER_DOMAIN = 2


def domain_blacklist_check(domain) -> dict:
    """Check if a domain is blacklisted

    Args:
        domain (str): The domain to check

    Returns:
        dict: A dictionary containing the results of the blacklist check
    """
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


def list_aws_domains() -> tuple[list, dict, str]:
    """List all our domains in AWS Route53

    Returns:
        tuple: A tuple containing a list of domains, the response, and an error message
    """
    try:
        response = aws_route53domains_client.list_domains()
        return (
            response.get("Domains", []),
            response,
            "",
        )
    except ClientError as e:
        return [], None, str(e)


def register_aws_domain(domain_name: str) -> tuple[list, dict, str]:
    """Register a domain in AWS Route53

    Args:
        domain_name (str): The domain name to register

    Returns:
        tuple: A tuple containing the status code, the response, and an error message
    """
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

        if response.get("ResponseMetadata", {}).get("HTTPStatusCode", 500) != 500:
            send_slack_message(
                message="Domain purchased",
                webhook_urls=[URL_MAP["ops-domain-setup-notifications"]],
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"[{domain_name}]\n🔥 New Domain Purchased: {domain_name}",
                        },
                    }
                ],
            )

        return (
            response.get("ResponseMetadata", {}).get("HTTPStatusCode", 500),
            response,
            "",
        )
    except ClientError as e:
        return 500, None, str(e)


def check_aws_domain_availability(domain_name: str) -> tuple[list, dict, str]:
    """Check if a domain is available in AWS Route53

    Args:
        domain_name (str): The domain name to check

    Returns:
        tuple: A tuple containing the status code, the response, and an error message
    """
    try:
        response = aws_route53domains_client.check_domain_availability(
            DomainName=domain_name, IdnLangCode=""
        )
        return (
            response.get("Availability", "UNAVAILABLE") == "AVAILABLE",
            response,
            domain_name,
        )
    except ClientError as e:
        return False, None, str(e)


def get_tld_prices(tld: str) -> tuple[float, dict, str]:
    """Get the price of a Top Level Domain (TLD). For example: com, net, org

    Args:
        tld (str): The TLD to get the price for

    Returns:
        tuple: A tuple containing the price, the response, and an error message
    """
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


def find_domain(domain_name: str) -> tuple[bool, dict]:
    """Find a domain name

    Args:
        domain_name (str): The domain name to find

    Returns:
        tuple: A tuple containing the status and a dictionary of the domain information
    """
    is_available, _, _ = check_aws_domain_availability(domain_name)
    if is_available:
        price, _, _ = get_tld_prices(domain_name.split(".")[-1])
        return True, {
            "domain_name": domain_name,
            "price": price,
        }
    else:
        return False, {}


def find_similar_domains(key_title: str, current_tld: str) -> list[dict]:
    """Find similar domains using a heuristic of different, applicable prefixes and TLDs

    Args:
        key_title (str): The key title to use. For example `sellscale` in `withsellscale.com`
        current_tld (str): The current TLD. For example `com` in `withsellscale.com`

    Returns:
        list: A list of similar domains
    """
    # TODO: This is inneficient, we need a better way to do this
    # Consider: AWS GetDomainSuggestions
    prefixes = ["try", "with", "go", "use", "on"]
    suffixes = ["email", "mail", "go", "outreach"]
    tlds = list(set([current_tld, "com", "net"]))

    # Get the prices for the TLDs
    tld_prices = {}
    for tld in tlds:
        price, _, _ = get_tld_prices(tld)
        tld_prices[tld] = price

    # Create all possible domain permutations
    domain_permutations: set = set()
    for prefix in prefixes:
        for tld in tlds:
            domain_permutations.add(f"{prefix}{key_title}.{tld}")
    for suffix in suffixes:
        for tld in tlds:
            domain_permutations.add(f"{key_title}{suffix}.{tld}")

    # Grab current domains from the database
    owned_domains: list[Domain] = Domain.query.filter(
        Domain.domain.in_(domain_permutations)
    ).all()
    owned_domains_set: set = set()
    for domain in owned_domains:
        owned_domains_set.add(domain.domain)

    # Create a list of domains to check
    domains_to_check = list(domain_permutations - owned_domains_set)
    if not domains_to_check:
        return []

    # Check the availability of the domains
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(
            executor.map(
                check_aws_domain_availability,
                domains_to_check,
            )
        )

    similar_domains = []
    for result in results:
        if result[0]:  # If available
            price = tld_prices.get(result[2].split(".")[-1], -1.0)
            similar_domains.append(
                {
                    "domain_name": result[2],
                    "price": price,
                }
            )

    return similar_domains


def generate_dkim_tokens(domain_name: str) -> list[str]:
    """Generate DKIM tokens for a domain. Uses SESv1

    Args:
        domain_name (str): The domain name to generate DKIM tokens for

    Returns:
        list: A list of DKIM tokens
    """
    # Generate DKIM tokens for the domain
    try:
        response = aws_ses_client.verify_domain_dkim(Domain=domain_name)
        return response["DkimTokens"]
    except:
        return []

    ### Using SESv2 ###
    # try:
    #     response = aws_sesv2_client.delete_email_identity(EmailIdentity=domain_name)
    # except:
    #     pass
    # response = aws_sesv2_client.create_email_identity(
    #     EmailIdentity=domain_name,
    #     DkimSigningAttributes={"NextSigningKeyLength": "RSA_2048_BIT"},
    # )
    # return response.get("DkimAttributes", {}).get("Tokens", [])


def verify_domain_identity(domain_name: str) -> str:
    """Verify a domain identity. Uses SESv1

    Args:
        domain_name (str): The domain name to verify

    Returns:
        str: The verification token
    """
    try:
        response = aws_ses_client.verify_domain_identity(Domain=domain_name)
        token = response["VerificationToken"]
        return token
    except ClientError as error:
        print(error)
        return ""


def get_aws_dkim_records(domain_name: str) -> Optional[str]:
    """Get the DKIM records for an AWS domain

    Args:
        domain_name (str): The domain name to get the DKIM records for

    Returns:
        str: The DKIM record
    """
    hosted_zone_id = get_hosted_zone_id(domain_name)
    if hosted_zone_id is None:
        return None

    records = aws_route53_client.list_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        StartRecordName="_domainkey." + domain_name,
        StartRecordType="CNAME",
    )
    records = records["ResourceRecordSets"]

    for record in records:
        if "_domainkey." + domain_name in record["Name"]:
            resource_record = record["ResourceRecords"][0]["Value"]
            return resource_record

    return None


def get_hosted_zone_id(domain_name: str) -> Optional[str]:
    """Get the hosted zone ID for a domain

    Args:
        domain_name (str): The domain name to get the hosted zone ID for

    Returns:
        str: The hosted zone ID
    """
    paginator = aws_route53_client.get_paginator("list_hosted_zones")

    for page in paginator.paginate():
        for zone in page["HostedZones"]:
            if zone["Name"] == domain_name.rstrip(".") + ".":
                return zone["Id"].split("/")[-1]

    return None


def is_valid_email_forwarding(
    original_domain: str, target_domain: Optional[str] = None
) -> bool:
    """Check if the original domain forwards to the target domain.

    Args:
        original_domain (str): The original domain to check
        target_domain (Optional[str], optional): The target domain to check against. Defaults to None.

    Returns:
        bool: True if the original domain forwards to the target domain, else False
    """
    # Get only the base part of the original domain
    original_domain = (
        original_domain.replace("http://", "")
        .replace("https://", "")
        .replace("www.", "")
    )

    # Attempt to get the final URL after redirects
    tests = ["http://", "https://", "http://www.", "https://www."]
    for test in tests:
        time.sleep(1)
        attempts = 0
        max_redirects = 5
        final_url = ""
        base_url = test + original_domain
        base_url_copy = base_url
        while attempts < max_redirects:
            if base_url == target_domain:
                final_url = base_url
                break
            try:
                attempts += 1
                response = requests.get(base_url, allow_redirects=False)
                if response.status_code == 200:
                    final_url = response.url
                    break
                elif (
                    response.status_code == 302
                    or response.status_code == 301
                    or response.status_code == 307
                    or response.status_code == 308
                ):
                    base_url = response.headers["Location"]
                    print(base_url)
                    continue
                elif response.status_code == 429:
                    print("Too many requests, wait 2 seconds")
                    send_slack_message(
                        message=f"Too many requests for {base_url_copy}, waiting 2 seconds",
                        webhook_urls=[URL_MAP["eng-sandbox"]],
                    )
                    time.sleep(2)
                    attempts -= 1
                    continue
                elif response.status_code == 403:
                    print("Forbidden, wait random time between 2 and 5 seconds")
                    send_slack_message(
                        message=f"Forbidden for {base_url_copy}, waiting random time between 2 and 5 seconds",
                        webhook_urls=[URL_MAP["eng-sandbox"]],
                    )
                    time.sleep(random.randint(2, 5))
                    continue
                else:
                    send_slack_message(
                        message=f"Domain forwarding error for {base_url_copy}: {response.status_code} - {response.reason}",
                        webhook_urls=[URL_MAP["eng-sandbox"]],
                    )
                    return False
            except Exception as e:
                send_slack_message(
                    message="Domain forwarding error: " + str(e),
                    webhook_urls=[URL_MAP["eng-sandbox"]],
                )
                print(f"Error checking domain forwarding: {e}")
                return False

        if not target_domain:
            if final_url != base_url:
                send_slack_message(
                    message=f"SUCCESS: Domain {base_url_copy} is redirecting to {final_url}",
                    webhook_urls=[URL_MAP["eng-sandbox"]],
                )
                print(f"{base_url_copy} forwards to {final_url}")
        else:
            if final_url == target_domain:
                send_slack_message(
                    message=f"SUCCESS: Domain {base_url_copy} is redirecting to {final_url}",
                    webhook_urls=[URL_MAP["eng-sandbox"]],
                )
                print(f"{base_url_copy} forwards to {target_domain}")
            else:
                send_slack_message(
                    message=f"FAIL: Domain {base_url_copy} is redirecting to {final_url}, but not to {target_domain}",
                    webhook_urls=[URL_MAP["eng-sandbox"]],
                )
                print(
                    f"{base_url_copy} is redirected to {final_url}, but not to {target_domain}"
                )
                return False

    return True


@celery.task
def setup_managed_inboxes(
    client_sdr_id: int, usernames: Optional[list[str]] = None
) -> tuple[bool, str]:
    """Setup managed inboxes for a client SDR. Will purchase a domain if necessary.

    Args:
        client_sdr_id (int): The ID of the client SDR
        usernames (Optional[str], optional): Usernames to use. Defaults to None.

    Returns:
        tuple: A tuple containing the status and a message
    """
    client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not client_sdr:
        return False, "SDR not found"

    client: Client = Client.query.get(client_sdr.client_id)
    if not client:
        return False, "Client not found"

    # Check if the client has an available domain
    registering_domain = False
    managed_domain: Domain = None
    available_domains = get_available_domains(client_id=client.id)
    if len(available_domains) == 0:
        # If no domain is found, create it
        if not client.domain:
            return False, "Client does not have a domain set"
        anchor_domain = client.domain
        if anchor_domain:
            # Clean it up
            anchor_domain = (
                anchor_domain.replace("http://", "")
                .replace("https://", "")
                .replace("www.", "")
                .split(".")[0]
                .strip("/")
            )
        anchor_tld = anchor_domain.split(".")[-1].strip("/")
        potential_domains = find_similar_domains(
            key_title=anchor_domain, current_tld=anchor_tld
        )
        if len(potential_domains) == 0:
            return False, "No similar domains found"
        similar_domain = potential_domains[0].get("domain_name")

        # Register the domain
        success, message, domain_id = domain_purchase_workflow(
            client_id=client.id, domain_name=similar_domain
        )
        if not success:
            return False, message
        managed_domain = Domain.query.get(domain_id)
        registering_domain = True
    else:
        managed_domain = Domain.query.get(available_domains[0].get("id"))

    # Get 2 usernames from the SDRs name
    first_name = get_first_name_from_full_name(client_sdr.name)
    last_name = get_last_name_from_full_name(client_sdr.name)
    first_username = first_name.lower()
    first_dot_last = f"{first_name.lower()}.{last_name.lower()}"

    # Setup workmail inboxes
    from src.automation.orchestrator import add_process_for_future

    wait_time = 45 if registering_domain else 0
    add_process_for_future(
        type="workmail_setup_workflow",
        args={
            "client_sdr_id": client_sdr_id,
            "domain_id": managed_domain.id,
            "username": (
                usernames[0] if (usernames and len(usernames) >= 1) else first_username
            ),
            "wait_for_domain": True,
        },
        minutes=wait_time,
    )
    add_process_for_future(
        type="workmail_setup_workflow",
        args={
            "client_sdr_id": client_sdr_id,
            "domain_id": managed_domain.id,
            "username": (
                usernames[1] if (usernames and len(usernames) >= 2) else first_dot_last
            ),
            "wait_for_domain": True,
        },
        minutes=wait_time,
    )

    return (
        True,
        "Managed inboxes setup workflow initiated. This will take at least 1 hour to complete.",
    )


@celery.task
def workmail_setup_workflow(
    client_sdr_id: int,
    domain_id: int,
    username: str,
    wait_for_domain: bool = False,
) -> tuple:
    """Workflow to setup a workmail inbox after domain is purchased.

    This includes:
    1. Create workmail inbox
    2. Add to smartlead

    Args:
        client_sdr_id (int): The ID of the client SDR
        domain_id (int): The ID of the domain
        username (str): The username of the inbox
        wait_for_domain (bool, optional): Whether to wait for the domain to be registered. Defaults to False.

    Returns:
        tuple: A tuple containing the status and a message
    """
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return False, "SDR not found"

    domain: Domain = Domain.query.get(domain_id)
    if not domain:
        return False, "Domain not found"
    domain_name = domain.domain
    # Check that the domain is registered
    if domain.aws_domain_registration_status != "SUCCESSFUL":
        if wait_for_domain:
            from src.automation.orchestrator import add_process_for_future

            add_process_for_future(
                type="workmail_setup_workflow",
                args={
                    "client_sdr_id": client_sdr_id,
                    "domain_id": domain_id,
                    "username": username,
                    "wait_for_domain": True,
                },
                minutes=10,
            )
            return True, "Domain not registered. But retrying in 10 minutes."

        return False, "Domain not registered"

    # Check that the domain only has MAX_INBOXES_PER_DOMAIN inboxes attached to it
    email_bank_count = SDREmailBank.query.filter_by(domain_id=domain_id).count()
    if email_bank_count > MAX_INBOXES_PER_DOMAIN:
        return False, "Domain has reached the maximum number of inboxes"

    # Generate a random password
    password = "".join(
        random.choice(string.ascii_uppercase + string.digits + string.ascii_lowercase)
        for _ in range(16)
    )

    # Registering the domain to workmail and creating the inbox
    success, _, email_bank_id = create_workmail_inbox(
        client_sdr_id=client_sdr_id,
        domain_id=domain_id,
        name=sdr.name,
        domain_name=domain_name,
        username=username,
        password=password,
    )
    if not success:
        return False, "Failed to create workmail inbox"

    # Add the domain_id to EmailBank
    sdr_email_bank: SDREmailBank = SDREmailBank.query.get(email_bank_id)
    sdr_email_bank.domain_id = domain_id
    db.session.commit()

    # Wait 10 seconds for the inbox to be created
    time.sleep(10)

    # Sync the workmail inbox to smartlead
    success, _, smartlead_account_id = sync_workmail_to_smartlead(
        client_sdr_id=client_sdr_id,
        username=f"{username}@{domain_name}",
        email=f"{username}@{domain_name}",
        password=password,
    )
    if not success:
        return False, "Failed to sync workmail inbox to smartlead"

    # Add the smartlead_id to EmailBank
    sdr_email_bank: SDREmailBank = SDREmailBank.query.get(email_bank_id)
    sdr_email_bank.smartlead_account_id = smartlead_account_id
    db.session.commit()

    # Sync the Smartlead inbox
    sync_email_bank_statistics_for_sdr.delay(client_sdr_id=client_sdr_id)

    return True, "Domain setup workflow completed successfully"


def create_workmail_inbox(
    client_sdr_id: int,
    domain_id: int,
    name: str,
    domain_name: str,
    username: str,
    password: str,
) -> tuple:
    """Create a workmail inbox for a domain

    Args:
        client_sdr_id (int): The ID of the ClientSDR
        domain_id (int): The ID of the Domain
        display_name (str): The display name of the inbox
        name (str): The name of the inbox
        domain_name (str): The domain name to create the inbox for
        username (str): The username of the inbox
        password (str): The password of the inbox

    Returns:
        tuple: A tuple containing the status, a message, and the EmailBankID
    """

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

    first_name = get_first_name_from_full_name(name)
    last_name = get_last_name_from_full_name(name)

    # Create a user and mailbox
    user = aws_workmail_client.create_user(
        OrganizationId=organization_id,
        DisplayName=f"{username}@{domain_name}",
        Name=f"{username}@{domain_name}",
        Password=password,
        FirstName=first_name,
        LastName=last_name,
    )

    # Assign an email address to the user
    user_id = user["UserId"]
    aws_workmail_client.register_to_work_mail(
        OrganizationId=organization_id,
        EntityId=user_id,
        Email=f"{username}@{domain_name}",
    )

    # Add to SDR Email Bank
    sdr_email_bank_id = create_sdr_email_bank(
        client_sdr_id=client_sdr_id,
        email_address=f"{username}@{domain_name}",
        email_type=EmailType.SELLSCALE,
        aws_workmail_user_id=user_id,
        aws_username=f"{username}@{domain_name}",
        aws_password=password,
        domain_id=domain_id,
    )

    send_slack_message(
        message="Inbox Setup",
        webhook_urls=[URL_MAP["ops-domain-setup-notifications"]],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"[{domain_name}]\n🙏 New Inbox Created on Smartlead: {username}@{domain_name}",
                },
            }
        ],
    )

    success = create_and_send_slack_notification_class_message(
        notification_type=SlackNotificationType.EMAIL_NEW_INBOX_CREATED,
        arguments={
            "client_sdr_id": client_sdr_id,
            "email": f"{username}@{domain_name}",
            "warmup_finish_date": (datetime.utcnow() + timedelta(days=14)).strftime(
                "%B %d, %Y"
            ),
        },
    )

    return True, "Workmail inbox created successfully", sdr_email_bank_id


def domain_purchase_workflow(
    client_id: int,
    domain_name: str,
) -> tuple[bool, str, int]:
    """Workflow to purchase a domain. Automatically queues up the domain setup workflow.

    Args:
        client_id (int): The ID of the client
        domain_name (str): The domain name to purchase

    Returns:
        tuple: A tuple containing the status, a message, and the domain ID
    """
    # Verify the client exists
    client: Client = Client.query.get(client_id)
    if not client:
        return False, "Client not found", -1

    # Register the domain
    status, response, error = register_aws_domain(domain_name)
    if status == 500:
        return False, f"Failed to purchase domain.\nError:{error}", -1

    operation_id = response.get("OperationId")

    # Add the domain to our DB
    domain_id = create_domain_entry(
        domain=domain_name,
        client_id=client_id,
        forward_to=client.domain or domain_name,
        aws=True,
        aws_domain_registration_job_id=operation_id,
        aws_autorenew_enabled=True,
    )

    from src.automation.orchestrator import add_process_for_future

    # In 30 min, setup the domain
    send_slack_message(
        message=f"{domain_name} Domain Registration in Progress, will attempt to setup in 30 minutes",
        webhook_urls=[URL_MAP["ops-domain-setup-notifications"]],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"[{domain_name}]\n🔥 Domain registration queued, will attempt to setup in 30 minutes",
                },
            }
        ],
    )
    add_process_for_future(
        type="domain_setup_workflow",
        args={"domain_name": domain_name, "domain_id": domain_id},
        minutes=30,
    )

    return True, "Domain purchase workflow completed successfully", domain_id


@celery.task
def domain_setup_workflow(
    domain_name: str,
    domain_id: int,
) -> tuple:
    """Workflow to setup a domain after domain is purchased.

    This includes:
    1. Add DNS records

    Args:
        domain_name (str): The domain name to setup

    Returns:
        tuple: A tuple containing the status and a message
    """
    # Get the Domain
    domain: Domain = Domain.query.get(domain_id)
    if not domain:
        return False, "Domain not found"

    # Verify that the domain is successfully registered
    if domain.aws_domain_registration_job_id:
        response = aws_route53domains_client.get_operation_detail(
            OperationId=domain.aws_domain_registration_job_id
        )
        status = response.get("Status")
        domain.aws_domain_registration_status = status
        db.session.commit()

        # In 15 min, setup the domain
        if status == "IN_PROGRESS":
            from src.automation.orchestrator import add_process_for_future

            send_slack_message(
                message=f"{domain_name} Domain Setup delayed for 30 minutes due to registration in progress",
                webhook_urls=[URL_MAP["ops-domain-setup-notifications"]],
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"[{domain_name}]\n🔥 Domain registration still in progress... will attempt to setup in another 30 minutes",
                        },
                    }
                ],
            )
            add_process_for_future(
                type="domain_setup_workflow",
                args={"domain_name": domain_name, "domain_id": domain_id},
                minutes=30,
            )

            return False, "Domain registration still in progress"

        if status != "SUCCESSFUL":
            return False, "Domain registration still in progress"

    # Get the hosted zone ID
    hosted_zone_id = get_hosted_zone_id(domain_name)
    if hosted_zone_id is None:
        return False, "Hosted zone not found for domain"
    domain.aws_hosted_zone_id = hosted_zone_id
    db.session.commit()

    # Add DNS records
    success, _ = add_email_dns_records(domain_id=domain_id, domain_name=domain_name)
    if not success:
        return False, "Failed to add email DNS records"

    # Configure email forwarding
    success, _ = configure_email_forwarding(
        domain_name=domain_name, domain_id=domain_id
    )
    if not success:
        return False, "Failed to configure email forwarding"

    return True, "Domain setup workflow completed successfully"


def add_email_dns_records(domain_id: int, domain_name: str) -> tuple[bool, str]:
    """Adds DNS records for a domain. Namely DKIM, DMARC, SPF, MX, and verification records

    Args:
        domain_id (int): The ID of the Domain object
        domain_name (str): The domain name to add DNS records for

    Returns:
        tuple: A tuple containing the status and a message
    """
    # Verify that this is a Hosted Zone belonging to us
    hosted_zone_id = get_hosted_zone_id(domain_name)
    if hosted_zone_id is None:
        return False, "Hosted zone not found for domain"

    # Get the Domain object
    domain: Domain = Domain.query.get(domain_id)
    if not domain:
        return False, "Domain not found"

    # Refresh our internal DNS record stores to make sure we don't perform redundant work
    _ = validate_domain_configuration(domain_id=domain_id)
    domain: Domain = Domain.query.get(domain_id)
    if domain.dmarc_record or domain.spf_record or domain.dkim_record:
        return False, "DNS records already exist"

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
                    "Value": f'"v=DMARC1; p=none; rua=mailto:sellscale@{domain_name}; ruf=mailto:sellscale@{domain_name}"'
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
            "ResourceRecords": [{"Value": '"v=spf1 include:amazonses.com ~all"'}],
        },
    }

    # MX record
    mx_record = {
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": domain_name,
            "Type": "MX",
            "TTL": 300,
            "ResourceRecords": [
                {"Value": "10 inbound-smtp.{}.amazonaws.com".format("us-east-1")}
            ],
        },
    }

    # Verification record
    verification_record = {
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": f"_amazonses.{domain_name}",
            "Type": "TXT",
            "TTL": 300,
            "ResourceRecords": [{"Value": f'"{verify_domain_identity(domain_name)}"'}],
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
                mx_record,
                verification_record,
            ]
        },
    )

    send_slack_message(
        message="Domain Records Set up",
        webhook_urls=[URL_MAP["ops-domain-setup-notifications"]],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""[{domain_name}]\n✈️ Domain Records Set up: {domain_name}
✅ DKIM
✅ DMARC
✅ SPF""",
                },
            }
        ],
    )

    return (
        True,
        "DNS records added successfully",
    )


def delete_workmail_inbox(workmail_user_id: str) -> tuple[bool, str]:
    """Delete a workmail inbox for an email

    Args:
        workmail_user_id (str): The ID of the workmail user

    Returns:
        tuple: A tuple containing the status and a message
    """
    try:
        organization_id = os.environ.get("AWS_WORKMAIL_ORG_ID")
        response = aws_workmail_client.deregister_from_work_mail(
            OrganizationId=organization_id, EntityId=workmail_user_id
        )
        response_metadata = response.get("ResponseMetadata", {})
        status_code = response_metadata.get("HTTPStatusCode", 500)
        if status_code == 200:
            return True, "Workmail inbox deleted successfully"
    except Exception as e:
        return False, f"Failed to delete workmail inbox: {e}"

    return False, "Failed to delete workmail inbox"


def delete_domain(domain_id: int) -> tuple[bool, str]:
    """Delete a domain (turn off auto-renewal)

    Args:
        domain_id (int): The ID of the Domain object

    Returns:
        tuple: A tuple containing the status and a message
    """
    domain: Domain = Domain.query.get(domain_id)

    # Make sure we don't delete a domain with active inboxes
    email_banks = SDREmailBank.query.filter_by(domain_id=domain.id).count()
    if email_banks > 0:
        return False, "Domain has active inboxes. Please remove them first"

    # Delete the domain (disable auto-renewal)
    try:
        result = aws_route53domains_client.disable_domain_auto_renew(
            DomainName=domain.domain
        )
        if result.get("ResponseMetadata", {}).get("HTTPStatusCode", 500) != 200:
            return False, "Failed to disable domain auto-renewal"
    except Exception as e:
        return False, f"Failed to disable domain auto-renewal: {e}"

    # Mark the domain as auto-renewal disabled
    domain.aws_autorenew_enabled = False
    db.session.commit()

    return True, "Domain auto-renewal disabled successfully"


def configure_email_forwarding(domain_name: str, domain_id: int) -> tuple[bool, str]:
    """Configure email forwarding for a domain using the following steps:

    1. Create an AWS Amplify App (with custom redirect rules)
    2. Create an AWS Amplify Branch
    3. Create an AWS Amplify Domain Association (to our custom domain)

    Args:
        domain_name (str): The domain name to configure email forwarding for
        domain_id (int): The ID of the Domain object

    Returns:
        tuple[bool, str]: A tuple containing the status and a message
    """
    # Get the Domain
    domain: Domain = Domain.query.get(domain_id)
    if not domain:
        raise Exception("Domain not found")

    # Make sure we haven't already created an Amplify App
    if domain.aws_amplify_app_id:
        return False, "Email forwarding already configured"

    # Create an AWS Amplify App
    app_id = create_aws_amplify_app(
        custom_domain=domain_name,
        reroute_domain=domain.forward_to,
    )
    if not app_id:
        return False, "Failed to create Amplify App"

    # Create an AWS Amplify Branch
    create_aws_amplify_branch(app_id=app_id)

    # Create an AWS Amplify Domain Association
    create_aws_amplify_domain_association(
        app_id=app_id,
        domain_name=domain_name,
    )

    # Update the domain object
    success = patch_domain_entry(
        domain_id=domain_id,
        aws_amplify_app_id=app_id,
    )
    if not success:
        return False, "Failed to update domain object"

    # Send a slack message
    send_slack_message(
        message="Email Forwarding Configured",
        webhook_urls=[URL_MAP["ops-domain-setup-notifications"]],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""[{domain_name}]\n📧 Email Forwarding Configured: {domain_name}
✅ AWS Amplify App
✅ AWS Amplify Branch
✅ AWS Amplify Domain Association""",
                },
            }
        ],
    )

    return True, "Email forwarding configured successfully"


def create_domain_entry(
    domain: str,
    client_id: int,
    forward_to: str,
    aws: bool,
    aws_domain_registration_job_id: Optional[str] = None,
    aws_domain_registration_status: Optional[str] = None,
    aws_hosted_zone_id: Optional[str] = None,
    aws_autorenew_enabled: Optional[bool] = None,
    dmarc_record: Optional[str] = None,
    spf_record: Optional[str] = None,
    dkim_record: Optional[str] = None,
) -> int:
    """Creates a Domain object

    Args:
        domain (str): The domain name
        client_id (int): The ID of the client
        forward_to (str): The domain to forward to
        aws (bool): Whether the domain is hosted on AWS
        aws_domain_registration_job_id (Optional[str], optional): The ID of the AWS Domain Registration Job. Defaults to None.
        aws_domain_registration_status (Optional[str], optional): The status of the AWS Domain Registration. Defaults to None.
        aws_hosted_zone_id (Optional[str], optional): The ID of the AWS Hosted Zone. Defaults to None.
        aws_autorenew_enabled (Optional[bool], optional): Whether auto-renewal is enabled. Defaults to None.
        dmarc_record (Optional[str], optional): The DMARC record. Defaults to None.
        spf_record (Optional[str], optional): The SPF record. Defaults to None.
        dkim_record (Optional[str], optional): The DKIM record. Defaults to None.

    Returns:
        int: ID of the created Domain object
    """
    domain = Domain(
        domain=domain,
        client_id=client_id,
        forward_to=forward_to,
        aws=aws,
        aws_domain_registration_job_id=aws_domain_registration_job_id,
        aws_domain_registration_status=aws_domain_registration_status,
        aws_hosted_zone_id=aws_hosted_zone_id,
        aws_autorenew_enabled=aws_autorenew_enabled,
        dmarc_record=dmarc_record,
        spf_record=spf_record,
        dkim_record=dkim_record,
        last_refreshed=datetime.utcnow(),
    )
    db.session.add(domain)
    db.session.commit()

    if dmarc_record or spf_record or dkim_record:
        validate_domain_configuration(domain.id)

    return domain.id


def patch_domain_entry(
    domain_id: int,
    forward_to: Optional[str] = None,
    aws: Optional[bool] = None,
    aws_hosted_zone_id: Optional[str] = None,
    aws_amplify_app_id: Optional[str] = None,
    dmarc_record: Optional[str] = None,
    spf_record: Optional[str] = None,
    dkim_record: Optional[str] = None,
) -> bool:
    """Patches a Domain object

    Args:
        domain_id (int): The ID of the Domain object to patch
        forward_to (Optional[str], optional): The domain to forward to. Defaults to None.
        aws (Optional[bool], optional): Whether the domain is hosted on AWS. Defaults to None.
        aws_hosted_zone_id (Optional[str], optional): The ID of the AWS Hosted Zone. Defaults to None.
        aws_amplify_app_id (Optional[str], optional): The ID of the AWS Amplify App. Defaults to None.
        dmarc_record (Optional[str], optional): The DMARC record. Defaults to None.
        spf_record (Optional[str], optional): The SPF record. Defaults to None.
        dkim_record (Optional[str], optional): The DKIM record. Defaults to None.

    Returns:
        bool: True if successful, else False
    """
    domain: Domain = Domain.query.get(domain_id)
    if not domain:
        return False

    if forward_to is not None:
        domain.forward_to = forward_to
    if aws is not None:
        domain.aws = aws
    if aws_hosted_zone_id is not None:
        domain.aws_hosted_zone_id = aws_hosted_zone_id
    if aws_amplify_app_id is not None:
        domain.aws_amplify_app_id = aws_amplify_app_id
    if dmarc_record is not None:
        domain.dmarc_record = dmarc_record
    if spf_record is not None:
        domain.spf_record = spf_record
    if dkim_record is not None:
        domain.dkim_record = dkim_record

    domain.last_refreshed = datetime.utcnow()

    db.session.commit()
    return True


@celery.task
def validate_all_domain_configurations() -> bool:
    """Validates the configuration of all domains

    Returns:
        bool: True if valid, else False
    """
    domains: list[Domain] = Domain.query.all()
    for i, domain in enumerate(domains):
        validate_domain_configuration.apply_async([domain.id], countdown=i * 5)

    return True


@celery.task
def validate_domain_configuration_for_client(client_id: int) -> bool:
    """Validates the configuration of all domains for a client

    Args:
        client_id (int): The ID of the client

    Returns:
        bool: True if valid, else False
    """
    domains: list[Domain] = Domain.query.filter_by(client_id=client_id).all()
    for domain in domains:
        validate_domain_configuration(domain.id)

    return True


@celery.task
def validate_domain_configuration(domain_id: int) -> bool:
    """Validates the configuration of a domain

    Args:
        domain_id (int): The ID of the Domain object to validate

    Returns:
        bool: True if valid, else False
    """
    domain: Domain = Domain.query.get(domain_id)
    if not domain:
        return False

    spf_record, spf_valid = spf_record_valid(domain=domain.domain)
    dmarc_record, dmarc_valid = dmarc_record_valid(domain=domain.domain)
    dkim_record, dkim_valid = dkim_record_valid(domain=domain.domain)

    domain.spf_record = spf_record
    domain.spf_record_valid = spf_valid
    domain.dmarc_record = dmarc_record
    domain.dmarc_record_valid = dmarc_valid
    domain.dkim_record = dkim_record
    domain.dkim_record_valid = dkim_valid

    valid = is_valid_email_forwarding(
        original_domain=domain.domain, target_domain=domain.forward_to
    )
    domain.forwarding_enabled = valid
    db.session.commit()

    domain.last_refreshed = datetime.utcnow()
    db.session.commit()

    return True


def get_available_domains(client_id: int) -> list[dict]:
    """Get all available domains for a client. Available domains are domains that have less than MAX_INBOXES_PER_DOMAIN inboxes

    Args:
        client_id (int): The ID of the client

    Returns:
        list[dict]: A list of available domains
    """
    query = (
        db.session.query(Domain, func.count(SDREmailBank.id).label("count"))
        .outerjoin(SDREmailBank, Domain.id == SDREmailBank.domain_id)
        .filter(
            Domain.client_id == client_id,
            Domain.aws_domain_registration_status == "SUCCESSFUL",
        )
        .group_by(Domain.id)
        .having(func.count(SDREmailBank.id) < MAX_INBOXES_PER_DOMAIN)
    )

    result = []
    for domain, count in query:
        result.append(
            {
                "id": domain.id,
                "domain": domain.domain,
                "count": count,
            }
        )

    return result


def get_domain_details(client_id: int) -> bool:
    """Gets all domain details, including both Domain and SDREmailBank

    Args:
        client_id (int): The ID of the client

    Returns:
        bool: True if successful, else False
    """
    domains: list[Domain] = Domain.query.filter_by(client_id=client_id).all()

    result = []
    for domain in domains:
        domain_dict = domain.to_dict()
        domain_dict["inboxes"] = []

        # Get the inboxes for the domain
        sdr_email_banks: list[SDREmailBank] = SDREmailBank.query.filter(
            SDREmailBank.domain_id == domain.id,
            SDREmailBank.smartlead_account_id != None,
        ).all()
        domain_dict["inboxes"] = [
            sdr_email_bank.to_dict() for sdr_email_bank in sdr_email_banks
        ]

        result.append(domain_dict)

    return result


# DEPRECATE ME ONCE THERE IS NO MORE SMARTLEAD
def backfill_warmup_snapshots_into_domains():
    """Backfills warmup snapshots into domains"""
    from src.warmup_snapshot.models import WarmupSnapshot
    from src.prospecting.models import ProspectChannels

    # Get all warmup_snapshots
    warmup_snapshots: list[WarmupSnapshot] = WarmupSnapshot.query.filter_by(
        channel_type=ProspectChannels.EMAIL
    )

    for snapshot in warmup_snapshots:
        domain = snapshot.account_name.split("@")[-1]
        existing_domain = Domain.query.filter_by(domain=domain).first()

        if not existing_domain:
            sdr: ClientSDR = ClientSDR.query.get(snapshot.client_sdr_id)
            client: Client = Client.query.get(sdr.client_id)
            new_domain = Domain(
                client_id=sdr.client_id,
                domain=domain,
                forward_to=client.domain or domain,
                aws=False,
            )
            db.session.add(new_domain)
            db.session.commit()

    return True
