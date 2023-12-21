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
