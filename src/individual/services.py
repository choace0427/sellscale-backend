import json
import math
from typing import Optional

from psycopg2 import IntegrityError
from src.company.services import find_company
from src.individual.models import Individual
from src.prospecting.models import Prospect
from sqlalchemy import or_

from src.company.models import Company, CompanyRelation
from src.research.models import IScraperPayloadCache
from app import db, celery
from src.utils.math import get_unique_int
from src.utils.slack import send_slack_message, URL_MAP


def backfill_prospects(client_sdr_id):

    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
    ).all()

    total_count = 0
    dupe_count = 0
    for prospect in prospects:
        success = add_individual_from_prospect(prospect.id)
        if not success: dupe_count += 1
        total_count += 1

    added_count = total_count - dupe_count

    send_slack_message(
        message=f"Backfilled {total_count} prospects to individuals, {added_count} added, {dupe_count} duplicates.",
        webhook_urls=[URL_MAP["csm-individuals"]],
    )

    return {
        "total_count": total_count,
        "dupe_count": dupe_count,
        "added_count": added_count,
    }


def add_individual_from_prospect(prospect_id: int) -> bool:

    prospect: Prospect = Prospect.query.get(prospect_id)
    if prospect.individual_id:
        return False
    
    # TODO: Update the individual with updated prospect data
    
    individual_id, created = add_individual(
        full_name=prospect.full_name,
        first_name=prospect.first_name,
        last_name=prospect.last_name,
        title=prospect.title,
        bio=prospect.linkedin_bio,
        linkedin_url=prospect.linkedin_url,
        instagram_url=None,
        facebook_url=None,
        twitter_url=prospect.twitter_url,
        email=prospect.email,
        phone=None,
        address=None,
        li_public_id=prospect.linkedin_url.split("/in/")[1].split("/")[0] if prospect.linkedin_url else None,
        li_urn_id=prospect.li_urn_id,
        img_url=prospect.img_url,
        img_expire=prospect.img_expire,
        industry=prospect.industry,
        company_name=prospect.company,
        company_id=prospect.company_id,
        linkedin_followers=None,
        instagram_followers=None,
        facebook_followers=None,
        twitter_followers=None,
    )
    prospect.individual_id = individual_id
    db.session.commit()

    return True if individual_id else False


def add_individual(
    full_name: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    title: Optional[str],
    bio: Optional[str],
    linkedin_url: Optional[str],
    instagram_url: Optional[str],
    facebook_url: Optional[str],
    twitter_url: Optional[str],
    email: Optional[str],# Unique
    phone: Optional[str],
    address: Optional[str],
    li_public_id: Optional[str],# Unique
    li_urn_id: Optional[str],# Unique
    img_url: Optional[str],
    img_expire: Optional[int],
    industry: Optional[str],
    company_name: Optional[str],
    company_id: Optional[str],
    linkedin_followers: Optional[int],
    instagram_followers: Optional[int],
    facebook_followers: Optional[int],
    twitter_followers: Optional[int],
) -> tuple[Optional[int], bool]:
    """
      Adds an individual to the database, or updates an existing individual if
      the email or li_public_id already exists.

      Returns the individual id and if a new record was created.
    """

    # If there's no email, li_public_id, or li_urn_id it will be hard to find so we can't add it
    if not email and not li_public_id and not li_urn_id:
        send_slack_message(
            message=f"Warning: Individual {full_name} has no email, li_public_id, or li_urn_id. Will not be added.",
            webhook_urls=[URL_MAP["csm-individuals"]],
        )
        return None, False
    

    if email:
        existing_individual_email: Individual = Individual.query.filter(
            Individual.email == email,
        ).first()
    else:
        existing_individual_email = None

    if li_public_id:
        existing_individual_li_public_id: Individual = Individual.query.filter(
            Individual.li_public_id == li_public_id,
        ).first()
    else:
        existing_individual_li_public_id = None

    
    if existing_individual_email and existing_individual_li_public_id:
        if existing_individual_email.id != existing_individual_li_public_id.id:
            send_slack_message(
                message=f"Warning: Two individuals, {existing_individual_email.full_name} ({existing_individual_email.id}) and {existing_individual_li_public_id.full_name} ({existing_individual_li_public_id.id}) seem to be the same person. Please investigate and merge.",
                webhook_urls=[URL_MAP["csm-individuals"]],
            )
            return None, False
        else:
            existing_individual = existing_individual_li_public_id
    else:
        if existing_individual_email:
            existing_individual = existing_individual_email
        elif existing_individual_li_public_id:
            existing_individual = existing_individual_li_public_id
        else:
            existing_individual = None

    if company_name and not company_id:
        # Try and find company
        company_id = find_company(company_name)

    if not full_name:
        full_name = f"{first_name} {last_name}"

    if existing_individual:
        if full_name: existing_individual.full_name = full_name
        if first_name: existing_individual.first_name = first_name
        if last_name: existing_individual.last_name = last_name
        if title: existing_individual.title = title
        if bio: existing_individual.bio = bio
        if linkedin_url: existing_individual.linkedin_url = linkedin_url
        if instagram_url: existing_individual.instagram_url = instagram_url
        if facebook_url: existing_individual.facebook_url = facebook_url
        if twitter_url: existing_individual.twitter_url = twitter_url
        if email: existing_individual.email = email
        if phone: existing_individual.phone = phone
        if address: existing_individual.address = address
        if li_public_id: existing_individual.li_public_id = li_public_id
        if li_urn_id: existing_individual.li_urn_id = li_urn_id
        if img_url: existing_individual.img_url = img_url
        if img_expire: existing_individual.img_expire = img_expire
        if industry: existing_individual.industry = industry
        if company_name: existing_individual.company_name = company_name
        if company_id: existing_individual.company_id = company_id
        if linkedin_followers: existing_individual.linkedin_followers = linkedin_followers
        if instagram_followers: existing_individual.instagram_followers = instagram_followers
        if facebook_followers: existing_individual.facebook_followers = facebook_followers
        if twitter_followers: existing_individual.twitter_followers = twitter_followers
        db.session.commit()
        return existing_individual.id, False
    
    else:
        individual = Individual(
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            title=title,
            bio=bio,
            linkedin_url=linkedin_url,
            instagram_url=instagram_url,
            facebook_url=facebook_url,
            twitter_url=twitter_url,
            email=email if email else None,
            phone=phone,
            address=address,
            li_public_id=li_public_id if li_public_id else None,
            li_urn_id=li_urn_id if li_urn_id else None,
            img_url=img_url,
            img_expire=img_expire,
            industry=industry,
            company_name=company_name,
            company_id=company_id,
            linkedin_followers=linkedin_followers,
            instagram_followers=instagram_followers,
            facebook_followers=facebook_followers,
            twitter_followers=twitter_followers,
        )
        db.session.add(individual)
        db.session.commit()
        return individual.id, True


