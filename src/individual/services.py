import datetime
import json
import math
from typing import Optional

from psycopg2 import IntegrityError
import sqlalchemy
from src.analytics.services import flag_enabled
from src.utils.abstract.attr_utils import deep_get
from src.company.services import find_company
from src.individual.models import Individual, IndividualsUpload
from src.prospecting.models import Prospect
from sqlalchemy import or_, and_, not_, text

from src.company.models import Company, CompanyRelation
from src.research.models import IScraperPayloadCache, IScraperPayloadType
from app import db, celery
from src.utils.slack import send_slack_message, URL_MAP


def backfill_prospects(client_sdr_id):
    prospects: list[Prospect] = Prospect.query.filter(
        Prospect.client_sdr_id == client_sdr_id,
    ).all()

    total_count = 0
    dupe_count = 0
    for prospect in prospects:
        success = add_individual_from_prospect.delay(prospect.id)
        if not success:
            dupe_count += 1
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


def convert_to_prospects(
    client_sdr_id: int,
    individual_ids: list[int],
    client_archetype_id: Optional[int] = None,
    segment_id: Optional[int] = None,
):
    from src.automation.orchestrator import add_process_list

    if len(individual_ids) > 10:
        return add_process_list(
            type="convert_to_prospect",
            args_list=[
                {
                    "client_sdr_id": client_sdr_id,
                    "client_archetype_id": client_archetype_id,
                    "individual_id": individual_id,
                    "segment_id": segment_id,
                }
                for individual_id in individual_ids
            ],
            chunk_size=200,
            chunk_wait_minutes=4,
        )
    else:
        for individual_id in individual_ids:
            convert_to_prospect(
                client_sdr_id=client_sdr_id,
                individual_id=individual_id,
                client_archetype_id=client_archetype_id,
                segment_id=segment_id,
            )
        return []


@celery.task
def convert_to_prospect(
    client_sdr_id: int,
    individual_id: int,
    client_archetype_id: Optional[int] = None,
    segment_id: Optional[int] = None,
):
    from src.prospecting.services import add_prospect
    from src.client.models import ClientArchetype

    if client_archetype_id:
        archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    else:
        archetype: ClientArchetype = ClientArchetype.query.filter_by(
            client_sdr_id=client_sdr_id, is_unassigned_contact_archetype=True
        ).first()

    if not archetype or archetype.client_sdr_id != client_sdr_id:
        return None

    individual: Individual = Individual.query.get(individual_id)
    company: Company = (
        Company.query.get(individual.company_id) if individual.company_id else None
    )

    prospect_id = add_prospect(
        client_id=archetype.client_id,
        archetype_id=client_archetype_id,
        client_sdr_id=client_sdr_id,
        company=individual.company_name,
        company_url=company.career_page_url if company else None,
        employee_count=str(company.employees) if company else None,
        full_name=individual.full_name,
        industry=individual.industry,
        linkedin_url=individual.linkedin_url,
        linkedin_bio=individual.bio,
        linkedin_num_followers=individual.linkedin_followers,
        title=individual.title,
        twitter_url=individual.twitter_url,
        email=individual.email,
        individual_id=individual.id,
        allow_duplicates=False,
        score_prospect=True,
        research_payload=True,
        segment_id=segment_id,
    )

    return True, prospect_id


def start_crawler_on_linkedin_public_id(profile_id: str):
    from src.automation.orchestrator import add_process_for_future

    profile_url = f"linkedin.com/in/{profile_id}"
    success, new_id, created = add_individual_from_linkedin_url(profile_url)

    if new_id:
        add_process_for_future(
            type="run_icrawler",
            args={"individual_id": new_id},
        )


# Scrapes li individuals following similar profiles until it can't find any more
@celery.task
def individual_similar_profile_crawler(individual_id: int):
    if not flag_enabled("icrawler_enabled"):
        return

    from src.automation.orchestrator import add_process_list

    individual: Individual = Individual.query.get(individual_id)
    if (
        not individual
        or not individual.linkedin_similar_profiles
        or len(individual.linkedin_similar_profiles) == 0
    ):
        send_slack_message(
            message=f"[iCrawler 🪳]\n- Individual (# {individual_id}) has no similar profiles\n- Ending this crawl branch ❌",
            webhook_urls=[URL_MAP["operations-icrawler"]],
        )
        return False, []

    # Get similar profiles
    new_ids = []
    for profile in individual.linkedin_similar_profiles:
        try:
            profile_id = profile.get("profile_id")
            if not profile_id:
                continue

            profile_url = f'linkedin.com/in/{profile.get("profile_id")}'
            success, new_id, created = add_individual_from_linkedin_url(profile_url)

            if not success:
                send_slack_message(
                    message=f"[iCrawler 🪳]\n- Failed to add individual with profile '{profile_url}'\n- Data = Success: {success}, New ID: {new_id}, Created: {created}",
                    webhook_urls=[URL_MAP["operations-icrawler"]],
                )
                continue

            if not created:
                send_slack_message(
                    message=f"[iCrawler 🪳]\n- Updated existing individual (# {new_id}) with profile '{profile_url}'\n- Ending this crawl branch ❌",
                    webhook_urls=[URL_MAP["operations-icrawler"]],
                )
                continue
            else:
                if not flag_enabled("icrawler_enabled"):
                    continue

                # Continue the crawl...
                send_slack_message(
                    message=f"[iCrawler 🪳]\n- Added individual (# {new_id}) with profile '{profile_url}'\n- Continuing the crawl 👣👣🪳",
                    webhook_urls=[URL_MAP["operations-icrawler"]],
                )
                new_ids.append(new_id)

        except Exception as e:
            send_slack_message(
                message=f"[iCrawler 🪳]\n- Error when crawling on branch for individual (# {individual_id})\n- Data = {str(e)}\n- Ending this crawl branch ❌",
                webhook_urls=[URL_MAP["operations-icrawler"]],
            )
            continue

    add_process_list(
        type="run_icrawler",
        args_list=[{"individual_id": new_id} for new_id in new_ids],
        buffer_wait_minutes=10,
        append_to_end=True,
    )

    return True, new_ids


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def add_individual_from_linkedin_url(
    self, url: str, upload_id: Optional[int] = None
) -> tuple[bool, int or str, bool or None]:
    from src.research.linkedin.services import research_personal_profile_details
    from src.prospecting.services import (
        get_navigator_slug_from_url,
        get_linkedin_slug_from_url,
    )
    from src.research.services import create_iscraper_payload_cache

    try:
        if "/in/" in url:
            slug = get_linkedin_slug_from_url(url)
        elif "/lead/" in url:
            slug = get_navigator_slug_from_url(url)

        # Get iScraper payload
        iscraper_cache: IScraperPayloadCache = (
            IScraperPayloadCache.get_iscraper_payload_cache_by_linkedin_url(
                linkedin_url=url,
            )
        )
        if iscraper_cache and iscraper_cache.payload:
            payload = json.loads(iscraper_cache.payload)
        else:
            # Fetch payload from iScraper...
            payload = research_personal_profile_details(profile_id=slug)

        if payload.get("detail") == "Profile data cannot be retrieved." or not deep_get(
            payload, "first_name"
        ):
            return False, "Profile data cannot be retrieved."

        linkedin_url = "linkedin.com/in/{}".format(deep_get(payload, "profile_id"))

        if not iscraper_cache:
            # Cache payload
            cache_id = create_iscraper_payload_cache(
                linkedin_url=linkedin_url,
                payload=payload,
                payload_type=IScraperPayloadType.PERSONAL,
            )
            if not cache_id:
                return False, "Could not cache payload."

        # Add individual from cache
        return add_individual_from_iscraper_cache(linkedin_url, upload_id)

    except Exception as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)


def backfill_iscraper_cache(start_index: int, end_index: int):
    from src.automation.orchestrator import add_process_list

    caches: list[IScraperPayloadCache] = IScraperPayloadCache.query.filter(
        IScraperPayloadCache.id >= start_index,
        IScraperPayloadCache.id <= end_index,
        IScraperPayloadCache.payload_type == IScraperPayloadType.PERSONAL,
    ).all()

    return add_process_list(
        type="add_individual_from_iscraper_cache",
        args_list=[{"li_url": cache.linkedin_url} for cache in caches],
        chunk_size=100,
        chunk_wait_minutes=30,
        buffer_wait_minutes=1,
        append_to_end=True,
    )


@celery.task
def add_individual_from_iscraper_cache(li_url: str, upload_id: Optional[int] = None):
    iscraper_cache: IScraperPayloadCache = (
        IScraperPayloadCache.get_iscraper_payload_cache_by_linkedin_url(
            linkedin_url=li_url,
        )
    )
    cache: dict = (
        json.loads(iscraper_cache.payload)
        if iscraper_cache and iscraper_cache.payload
        else None
    )
    if not cache:
        return None

    # Try and find company
    company_name = deep_get(cache, "position_groups.0.company.name")
    company_id = find_company(company_name) if company_name else None

    individual_id, created = add_individual(
        full_name=cache.get("first_name") + " " + cache.get("last_name"),
        first_name=cache.get("first_name"),
        last_name=cache.get("last_name"),
        title=cache.get("sub_title"),
        bio=cache.get("summary"),
        linkedin_url=li_url,
        instagram_url=None,
        facebook_url=None,
        twitter_url=deep_get(cache, "contact_info.twitter"),
        email=deep_get(cache, "contact_info.email"),
        phone=None,
        address=None,
        li_public_id=cache.get("profile_id"),
        li_urn_id=cache.get("entity_urn"),
        img_url=None,
        img_expire=None,
        industry=cache.get("industry"),
        company_name=company_name,
        company_id=company_id,
        linkedin_followers=deep_get(cache, "network_info.followers_count"),
        instagram_followers=None,
        facebook_followers=None,
        twitter_followers=None,
        linkedin_connections=deep_get(cache, "network_info.connections_count"),
        linkedin_recommendations=cache.get("recommendations"),
        birth_date=cache.get("birth_date"),
        location=cache.get("location"),
        language_country=deep_get(cache, "languages.primary_locale.country"),
        language_locale=deep_get(cache, "languages.primary_locale.language"),
        skills=cache.get("skills"),
        websites=deep_get(cache, "contact_info.websites"),
        education_history=cache.get("education"),
        patent_history=cache.get("patents"),
        award_history=cache.get("awards"),
        certification_history=cache.get("certifications"),
        organization_history=cache.get("organizations"),
        project_history=cache.get("projects"),
        publication_history=cache.get("publications"),
        course_history=cache.get("courses"),
        test_score_history=cache.get("test_scores"),
        work_history=cache.get("position_groups"),
        volunteer_history=cache.get("volunteer_experiences"),
        linkedin_similar_profiles=cache.get("related_profiles"),
        recent_education_school=deep_get(cache, "education.0.school.name"),
        recent_education_degree=deep_get(cache, "education.0.degree_name"),
        recent_education_field=deep_get(cache, "education.0.field_of_study"),
        recent_education_start_date=(
            None
            if deep_get(cache, "education.0.date.start.month") is None
            or deep_get(cache, "education.0.date.start.year") is None
            else datetime.date(
                year=deep_get(cache, "education.0.date.start.year"),
                month=deep_get(cache, "education.0.date.start.month"),
                day=1,
            )
        ),
        recent_education_end_date=(
            None
            if deep_get(cache, "education.0.date.end.month") is None
            or deep_get(cache, "education.0.date.end.year") is None
            else datetime.date(
                year=deep_get(cache, "education.0.date.end.year"),
                month=deep_get(cache, "education.0.date.end.month"),
                day=1,
            )
        ),
        recent_job_title=deep_get(cache, "position_groups.0.profile_positions.0.title"),
        recent_job_start_date=(
            None
            if deep_get(cache, "position_groups.0.profile_positions.0.date.start.month")
            is None
            or deep_get(cache, "position_groups.0.profile_positions.0.date.start.year")
            is None
            else datetime.date(
                year=deep_get(
                    cache, "position_groups.0.profile_positions.0.date.start.year"
                ),
                month=deep_get(
                    cache, "position_groups.0.profile_positions.0.date.start.month"
                ),
                day=1,
            )
        ),
        recent_job_end_date=(
            None
            if deep_get(cache, "position_groups.0.profile_positions.0.date.end.month")
            is None
            or deep_get(cache, "position_groups.0.profile_positions.0.date.end.year")
            is None
            else datetime.date(
                year=deep_get(
                    cache, "position_groups.0.profile_positions.0.date.end.year"
                ),
                month=deep_get(
                    cache, "position_groups.0.profile_positions.0.date.end.month"
                ),
                day=1,
            )
        ),
        recent_job_description=deep_get(
            cache, "position_groups.0.profile_positions.0.description"
        ),
        recent_job_location=deep_get(
            cache, "position_groups.0.profile_positions.0.location"
        ),
        upload_id=upload_id,
    )

    return True if individual_id else False, individual_id, created


@celery.task
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
        li_public_id=(
            prospect.linkedin_url.split("/in/")[1].split("/")[0]
            if prospect.linkedin_url
            else None
        ),
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
        linkedin_connections=None,
        linkedin_recommendations=None,
        birth_date=None,
        location=None,
        language_country=None,
        language_locale=None,
        skills=None,
        websites=None,
        education_history=None,
        patent_history=None,
        award_history=None,
        certification_history=None,
        organization_history=None,
        project_history=None,
        publication_history=None,
        course_history=None,
        test_score_history=None,
        work_history=None,
        volunteer_history=None,
        linkedin_similar_profiles=None,
        recent_education_school=None,
        recent_education_degree=None,
        recent_education_field=None,
        recent_education_start_date=None,
        recent_education_end_date=None,
        recent_job_title=None,
        recent_job_start_date=None,
        recent_job_end_date=None,
        recent_job_description=None,
        recent_job_location=None,
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
    email: Optional[str],  # Unique
    phone: Optional[str],
    address: Optional[str],
    li_public_id: Optional[str],  # Unique
    li_urn_id: Optional[str],  # Unique
    img_url: Optional[str],
    img_expire: Optional[int],
    industry: Optional[str],
    company_name: Optional[str],
    company_id: Optional[str],
    linkedin_followers: Optional[int],
    instagram_followers: Optional[int],
    facebook_followers: Optional[int],
    twitter_followers: Optional[int],
    linkedin_connections: Optional[int],
    linkedin_recommendations: Optional[list[dict]],
    birth_date: Optional[str],
    location: Optional[dict],
    language_country: Optional[str],
    language_locale: Optional[str],
    skills: Optional[list[str]],
    websites: Optional[list[dict]],
    education_history: Optional[list[dict]],
    patent_history: Optional[list[dict]],
    award_history: Optional[list[dict]],
    certification_history: Optional[list[dict]],
    organization_history: Optional[list[dict]],
    project_history: Optional[list[dict]],
    publication_history: Optional[list[dict]],
    course_history: Optional[list[dict]],
    test_score_history: Optional[list[dict]],
    work_history: Optional[list[dict]],
    volunteer_history: Optional[list[dict]],
    linkedin_similar_profiles: Optional[list[dict]],
    recent_education_school: Optional[str],
    recent_education_degree: Optional[str],
    recent_education_field: Optional[str],
    recent_education_start_date: Optional[datetime.date],
    recent_education_end_date: Optional[datetime.date],
    recent_job_title: Optional[str],
    recent_job_start_date: Optional[datetime.date],
    recent_job_end_date: Optional[datetime.date],
    recent_job_description: Optional[str],
    recent_job_location: Optional[dict],
    upload_id: Optional[int] = None,
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
        if full_name:
            existing_individual.full_name = full_name
        if first_name:
            existing_individual.first_name = first_name
        if last_name:
            existing_individual.last_name = last_name
        if title:
            existing_individual.title = title
        if bio:
            existing_individual.bio = bio
        if linkedin_url:
            existing_individual.linkedin_url = linkedin_url
        if instagram_url:
            existing_individual.instagram_url = instagram_url
        if facebook_url:
            existing_individual.facebook_url = facebook_url
        if twitter_url:
            existing_individual.twitter_url = twitter_url
        if email:
            existing_individual.email = email
        if phone:
            existing_individual.phone = phone
        if address:
            existing_individual.address = address
        if li_public_id:
            existing_individual.li_public_id = li_public_id
        if li_urn_id:
            existing_individual.li_urn_id = li_urn_id
        if img_url:
            existing_individual.img_url = img_url
        if img_expire:
            existing_individual.img_expire = img_expire
        if industry:
            existing_individual.industry = industry
        if company_name:
            existing_individual.company_name = company_name
        if company_id:
            existing_individual.company_id = company_id
        if linkedin_followers:
            existing_individual.linkedin_followers = linkedin_followers
        if instagram_followers:
            existing_individual.instagram_followers = instagram_followers
        if facebook_followers:
            existing_individual.facebook_followers = facebook_followers
        if twitter_followers:
            existing_individual.twitter_followers = twitter_followers
        if linkedin_connections:
            existing_individual.linkedin_connections = linkedin_connections
        if linkedin_recommendations:
            existing_individual.linkedin_recommendations = linkedin_recommendations
        if birth_date:
            existing_individual.birth_date = birth_date
        if location:
            existing_individual.location = location
        if language_country:
            existing_individual.language_country = language_country
        if language_locale:
            existing_individual.language_locale = language_locale
        if skills:
            existing_individual.skills = skills
        if websites:
            existing_individual.websites = websites
        if education_history:
            existing_individual.education_history = education_history
        if patent_history:
            existing_individual.patent_history = patent_history
        if award_history:
            existing_individual.award_history = award_history
        if certification_history:
            existing_individual.certification_history = certification_history
        if organization_history:
            existing_individual.organization_history = organization_history
        if project_history:
            existing_individual.project_history = project_history
        if publication_history:
            existing_individual.publication_history = publication_history
        if course_history:
            existing_individual.course_history = course_history
        if test_score_history:
            existing_individual.test_score_history = test_score_history
        if work_history:
            existing_individual.work_history = work_history
        if volunteer_history:
            existing_individual.volunteer_history = volunteer_history
        if linkedin_similar_profiles:
            existing_individual.linkedin_similar_profiles = linkedin_similar_profiles
        if recent_education_school:
            existing_individual.recent_education_school = recent_education_school
        if recent_education_degree:
            existing_individual.recent_education_degree = recent_education_degree
        if recent_education_field:
            existing_individual.recent_education_field = recent_education_field
        if recent_education_start_date:
            existing_individual.recent_education_start_date = (
                recent_education_start_date
            )
        if recent_education_end_date:
            existing_individual.recent_education_end_date = recent_education_end_date
        if recent_job_title:
            existing_individual.recent_job_title = recent_job_title
        if recent_job_start_date:
            existing_individual.recent_job_start_date = recent_job_start_date
        if recent_job_end_date:
            existing_individual.recent_job_end_date = recent_job_end_date
        if recent_job_description:
            existing_individual.recent_job_description = recent_job_description
        if recent_job_location:
            existing_individual.recent_job_location = recent_job_location
        if upload_id:
            existing_individual.upload_id = upload_id

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
            linkedin_connections=linkedin_connections,
            linkedin_recommendations=linkedin_recommendations,
            birth_date=birth_date,
            location=location,
            language_country=language_country,
            language_locale=language_locale,
            skills=skills,
            websites=websites,
            education_history=education_history,
            patent_history=patent_history,
            award_history=award_history,
            certification_history=certification_history,
            organization_history=organization_history,
            project_history=project_history,
            publication_history=publication_history,
            course_history=course_history,
            test_score_history=test_score_history,
            work_history=work_history,
            volunteer_history=volunteer_history,
            linkedin_similar_profiles=linkedin_similar_profiles,
            recent_education_school=recent_education_school,
            recent_education_degree=recent_education_degree,
            recent_education_field=recent_education_field,
            recent_education_start_date=recent_education_start_date,
            recent_education_end_date=recent_education_end_date,
            recent_job_title=recent_job_title,
            recent_job_start_date=recent_job_start_date,
            recent_job_end_date=recent_job_end_date,
            recent_job_description=recent_job_description,
            recent_job_location=recent_job_location,
            upload_id=upload_id,
        )
        db.session.add(individual)
        db.session.commit()
        return individual.id, True


def get_uploads():
    uploads: list[IndividualsUpload] = (
        IndividualsUpload.query.order_by(
            IndividualsUpload.id.desc(),
        )
        .limit(100)
        .all()
    )
    return [upload.to_dict() for upload in uploads]


def start_upload(
    name: str,
    data: list[dict],
    client_id: Optional[int] = None,
    client_archetype_id: Optional[int] = None,
):
    from src.automation.orchestrator import add_process_list

    upload = IndividualsUpload(
        name=name,
        total_size=len(data),
        upload_size=0,
        payload_data=data,
        client_id=client_id,
        client_archetype_id=client_archetype_id,
    )
    db.session.add(upload)
    db.session.commit()

    jobs = []
    for d in data:
        li_url = d.get("linkedin_url")
        if li_url and "/in/" in li_url:
            profile_id = li_url.split("/in/")[1].split("/")[0]
            profile_url = f"linkedin.com/in/{profile_id}"
            if profile_id:
                jobs.append({"upload_id": upload.id, "profile_url": profile_url})

    upload: IndividualsUpload = IndividualsUpload.query.get(upload.id)
    upload.upload_size = len(jobs)
    db.session.commit()

    add_process_list(
        type="upload_job_for_individual",
        args_list=jobs,
        buffer_wait_minutes=1,
    )

    return upload.to_dict()


def start_upload_from_urn_ids(name: str, urn_ids: list[str]):
    from src.automation.orchestrator import add_process_list

    upload = IndividualsUpload(
        name=name,
        total_size=len(urn_ids),
        upload_size=0,
        payload_data=urn_ids,
    )
    db.session.add(upload)
    db.session.commit()

    jobs = []
    for urn_id in urn_ids:
        jobs.append({"upload_id": upload.id, "urn_id": urn_id})

    upload: IndividualsUpload = IndividualsUpload.query.get(upload.id)
    upload.upload_size = len(jobs)
    db.session.commit()

    add_process_list(
        type="upload_job_for_individual",
        args_list=jobs,
        buffer_wait_minutes=1,
    )

    return upload.to_dict()


@celery.task
def upload_job_for_individual(
    upload_id: int = None, profile_url: str = None, urn_id: str = None
):
    if not profile_url and urn_id:
        from src.voyager.linkedin import LinkedIn

        api = LinkedIn(34)  # Aaron's account
        profile = api.get_profile(urn_id=urn_id)
        if not profile or not profile.get("public_id"):
            return False
        profile_url = f'linkedin.com/in/{profile.get("public_id")}'

    if upload_id:
        upload: IndividualsUpload = IndividualsUpload.query.get(upload_id)
        if upload:
            upload.added_size = upload.added_size + 1 if upload.added_size else 1
            db.session.commit()

    result = add_individual_from_linkedin_url(profile_url, upload_id=upload_id)
    if type(result) is tuple:
        return result

    return True


def get_all_individuals(client_archetype_id: int, limit: int = 100, offset: int = 0):
    from src.prospecting.icp_score.models import ICPScoringRuleset
    from model_import import ClientArchetype

    # from src.vector_db.services import fetch_individuals

    ruleset: ICPScoringRuleset = ICPScoringRuleset.query.filter(
        ICPScoringRuleset.client_archetype_id == client_archetype_id,
    ).first()

    archetype: ClientArchetype = ClientArchetype.query.get(client_archetype_id)

    # Start building the query for the Individual table
    individuals_query = (
        Individual.query.join(Prospect, Prospect.individual_id == Individual.id)
        .join(Company, Company.id == Individual.company_id)
        .filter(
            ~db.session.query(Prospect)
            .filter(
                Prospect.individual_id == Individual.id,
                Prospect.client_id == archetype.client_id,
            )
            .correlate(Individual)
            .exists()
        )
    )

    if ruleset:
        # # Title
        if ruleset.included_individual_title_keywords:
            keyword_filters = [
                Individual.title.ilike(f"%{keyword}%")
                for keyword in ruleset.included_individual_title_keywords
            ]
            individuals_query = individuals_query.filter(or_(*keyword_filters))

        if ruleset.excluded_individual_title_keywords:
            exclude_filters = [
                not_(Individual.title.ilike(f"%{keyword}%"))
                for keyword in ruleset.excluded_individual_title_keywords
            ]
            individuals_query = individuals_query.filter(and_(*exclude_filters))

        # Seniority
        if ruleset.included_individual_seniority_keywords:
            keyword_filters = [
                Individual.title.ilike(f"%{keyword}%")
                for keyword in ruleset.included_individual_seniority_keywords
            ]
            individuals_query = individuals_query.filter(or_(*keyword_filters))

        if ruleset.excluded_individual_seniority_keywords:
            exclude_filters = [
                not_(Individual.title.ilike(f"%{keyword}%"))
                for keyword in ruleset.excluded_individual_seniority_keywords
            ]
            individuals_query = individuals_query.filter(and_(*exclude_filters))

        # # Industry
        if ruleset.included_individual_industry_keywords:
            keyword_filters = [
                Individual.industry.ilike(f"%{keyword}%")
                for keyword in ruleset.included_individual_industry_keywords
            ]
            individuals_query = individuals_query.filter(or_(*keyword_filters))

        if ruleset.excluded_individual_industry_keywords:
            exclude_filters = [
                not_(Individual.industry.ilike(f"%{keyword}%"))
                for keyword in ruleset.excluded_individual_industry_keywords
            ]
            individuals_query = individuals_query.filter(and_(*exclude_filters))

        # # Company
        if ruleset.included_company_name_keywords:
            keyword_filters = [
                Individual.company_name.ilike(f"%{keyword}%")
                for keyword in ruleset.included_company_name_keywords
            ]
            individuals_query = individuals_query.filter(or_(*keyword_filters))

        if ruleset.excluded_company_name_keywords:
            exclude_filters = [
                not_(Individual.company_name.ilike(f"%{keyword}%"))
                for keyword in ruleset.excluded_company_name_keywords
            ]
            individuals_query = individuals_query.filter(and_(*exclude_filters))

        # # Bio
        if ruleset.included_individual_generalized_keywords:
            keyword_filters = [
                Individual.bio.ilike(f"%{keyword}%")
                for keyword in ruleset.included_individual_generalized_keywords
            ]
            individuals_query = individuals_query.filter(or_(*keyword_filters))

        if ruleset.excluded_individual_generalized_keywords:
            exclude_filters = [
                not_(Individual.bio.ilike(f"%{keyword}%"))
                for keyword in ruleset.excluded_individual_generalized_keywords
            ]
            individuals_query = individuals_query.filter(and_(*exclude_filters))

        # # Location
        if ruleset.included_individual_locations_keywords:
            keyword_filters = [
                text("CAST(individual.location AS TEXT) ILIKE :keyword").bindparams(
                    keyword=rf"%{keyword}%"
                )
                for keyword in ruleset.included_individual_locations_keywords
            ]
            individuals_query = individuals_query.filter(or_(*keyword_filters))

        if ruleset.excluded_individual_locations_keywords:
            exclude_filters = [
                ~text("CAST(individual.location AS TEXT) ILIKE :keyword").bindparams(
                    keyword=rf"%{keyword}%"
                )
                for keyword in ruleset.excluded_individual_locations_keywords
            ]
            individuals_query = individuals_query.filter(and_(*exclude_filters))

        # # Skills
        if ruleset.included_individual_skills_keywords:
            keyword_filters = [
                Individual.skills.any(skill.ilike(f"%{keyword}%"))
                for keyword in ruleset.included_individual_skills_keywords
                for skill in Individual.skills
            ]
            individuals_query = individuals_query.filter(or_(*keyword_filters))

        if ruleset.excluded_individual_skills_keywords:
            exclude_filters = [
                ~Individual.skills.any(skill.ilike(f"%{keyword}%"))
                for keyword in ruleset.excluded_individual_skills_keywords
                for skill in Individual.skills
            ]
            individuals_query = individuals_query.filter(and_(*exclude_filters))

        # # Company Description
        if ruleset.included_company_generalized_keywords:
            keyword_filters = [
                Company.description.ilike(f"%{keyword}%")
                for keyword in ruleset.included_company_generalized_keywords
            ]
            individuals_query = individuals_query.filter(or_(*keyword_filters))

        if ruleset.excluded_company_generalized_keywords:
            exclude_filters = [
                not_(Company.description.ilike(f"%{keyword}%"))
                for keyword in ruleset.excluded_individual_skills_keywords
            ]
            individuals_query = individuals_query.filter(and_(*exclude_filters))

        # # Company Industry
        # # if ruleset.included_company_industries_keywords:
        # #     keyword_filters = [
        # #         text("CAST(company.industries AS TEXT) ILIKE :keyword").bindparams(
        # #             keyword=rf"%{keyword}%")
        # #         for keyword in ruleset.included_company_industries_keywords
        # #     ]
        # #     individuals_query = individuals_query.filter(or_(*keyword_filters))

        # # if ruleset.excluded_company_industries_keywords:
        # #     exclude_filters = [
        # #         ~Company.industries.any(keyword.ilike(f"%{keyword}%"))
        # #         for keyword in ruleset.excluded_company_industries_keywords
        # #     ]
        # #     keyword_filters = [
        # #         text("CAST(company.industries AS TEXT) ILIKE :keyword").bindparams(
        # #             keyword=rf"%{keyword}%")
        # #         for keyword in ruleset.included_company_industries_keywords
        # #     ]
        # #     individuals_query = individuals_query.filter(
        # #         and_(*exclude_filters))

        # # Company Employee Count
        if ruleset.company_size_start and ruleset.company_size_end:
            individuals_query = individuals_query.filter(
                Company.employees >= ruleset.company_size_start,
                Company.employees <= ruleset.company_size_end,
            )

        # Company has 'locations'. not location. cast location to string
        if ruleset.included_company_locations_keywords:
            include_location_filters = [
                Company.locations.cast(sqlalchemy.String).ilike(f"%{keyword}%")
                for keyword in ruleset.included_company_locations_keywords
            ]
            individuals_query = individuals_query.filter(or_(*include_location_filters))

        if ruleset.excluded_company_locations_keywords:
            exclude_location_filters = [
                not_(Company.locations.cast(sqlalchemy.String).ilike(f"%{keyword}%"))
                for keyword in ruleset.excluded_company_locations_keywords
            ]
            individuals_query = individuals_query.filter(
                and_(*exclude_location_filters)
            )

        # # TODO the rest of the filters
        # # Experience
        # # if ruleset.individual_years_of_experience_start and ruleset.individual_years_of_experience_end:
        # #     job_experience_filter = and_(
        # #         Individual.years_of_experience >= ruleset.individual_years_of_experience_start,
        # #         years_of_experience <= ruleset.individual_years_of_experience_end)

        # #     individuals_query = individuals_query.filter(job_experience_filter)

    # After applying all the filters, retrieve the filtered individuals
    filtered_individuals: list[Individual] = (
        individuals_query.limit(limit).offset(offset).all()
    )
    count_individuals = individuals_query.count()

    return [
        individual.to_dict() for individual in filtered_individuals
    ], count_individuals


def parse_work_history(work_history: list):
    import json

    # Parse each JSON string and extract useful info
    useful_info = []

    for data in work_history:
        try:
            # Parsing the JSON string
            company_name = data.get("company", {}).get("name")
            for position in data.get("profile_positions", []):

                start_data = position.get("date", {}).get("start")
                start_str = (
                    f"{start_data.get('month', '?')}/{start_data.get('year', '?')}"
                    if start_data
                    else None
                )

                end_data = position.get("date", {}).get("end")
                end_str = (
                    f"{end_data.get('month', '?')}/{end_data.get('year', '?')}"
                    if end_data
                    else None
                )

                position_info = {
                    "company_name": company_name,
                    "title": position.get("title"),
                    "start_date": start_str,
                    "end_date": end_str,
                }
                useful_info.append(position_info)
        except json.JSONDecodeError:
            continue  # If there's an error in decoding, we skip that entry

    return useful_info
