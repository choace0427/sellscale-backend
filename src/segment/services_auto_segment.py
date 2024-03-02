from httpx import Client
from sqlalchemy import and_, or_, not_, Integer, cast, func
from tqdm import tqdm
from model_import import (
    Prospect,
    Segment,
    ClientSDR,
    ClientArchetype,
    ResearchPayload,
    Client,
)
from app import db
from src.client.services import (
    list_prospects_caught_by_client_filters,
    list_prospects_caught_by_sdr_client_filters,
)
from src.prospecting.models import ProspectOverallStatus
from src.segment.services import (
    add_prospects_to_segment,
    get_prospect_ids_for_segment,
    remove_prospect_from_segment,
    wipe_and_delete_segment,
    wipe_segment_ids_from_prospects_in_segment,
)
from sqlalchemy import update

# PRE_FILTERS = {
#     "titles": [
#         "DevOps",
#         "DevSecOps",
#         "Platform Engineering",
#         "SRE",
#         "AppSec",
#         "Site Reliability",
#         "Security architects",
#         "App Security",
#         "Product security",
#         "Cloud architect",
#         "Software Security",
#         "Software engineer",
#         "security engineer",
#     ],
#     "seniority": [
#         "Senior",
#         "Sr.",
#         "Lead",
#         "Manager",
#         "Principal",
#         "Director",
#         "Head of ",
#         "VP",
#         "Vice President",
#     ],
#     "location": [
#         "San Francisco",
#         "Bay Area",
#         "San Jose",
#         "Santa Clara",
#         "Sunnyvale",
#         "Mountain View",
#         "Palo Alto",
#         "Redwood City",
#         "San Mateo",
#         "Fremont",
#         "Oakland",
#         "Berkeley",
#         "Emeryville",
#         "Alameda",
#         "San Leandro",
#         "Hayward",
#         "Union City",
#         "Newark",
#         "Pleasanton",
#         "Livermore",
#         "Dublin",
#         "San Ramon",
#         "Cupertino",
#     ],
#     "employee_count": {"min": 150, "max": 10000000},
# }


def find_all_do_not_contact_prospects(
    parent_segment_id: int,
    client_sdr_id: int,
    prospect_ids_in_segment: list[int],
    print_logs: bool = True,
):
    prospect_dicts_client = list_prospects_caught_by_client_filters(client_sdr_id)
    prospect_dics_sdrs = list_prospects_caught_by_sdr_client_filters(client_sdr_id)
    prospect_dicts = []
    if prospect_dicts_client:
        prospect_dicts.extend(prospect_dicts_client)
    if prospect_dics_sdrs:
        prospect_dicts.extend(prospect_dics_sdrs)

    # Filter prospect ids to only be the ones in the segment
    prospect_dicts = [
        x for x in prospect_dicts if x.get("id") in prospect_ids_in_segment
    ]

    if print_logs:
        print("")
        print("### FINDING DO NOT CONTACT PROSPECTS ###")
        print(
            "Found ",
            len(prospect_dicts),
            " prospects who are in the do not contact criteria ...",
        )

    # put all the prospects in a segment called "Z. ❌ Do Not Contact"
    segment: Segment = Segment(
        segment_title="Z. ❌ Do Not Contact",
        client_sdr_id=client_sdr_id,
        filters={},
        parent_segment_id=parent_segment_id,
    )
    db.session.add(segment)
    db.session.commit()

    batch_size = 100
    for i in tqdm(range(0, len(prospect_dicts), batch_size)):
        batch_prospects = prospect_dicts[i : i + batch_size]
        prospect_ids = [prospect["id"] for prospect in batch_prospects]

        add_prospects_to_segment(
            new_segment_id=segment.id,
            prospect_ids=prospect_ids,
        )

    if print_logs:
        print("Added ", len(prospect_dicts), " prospects to segment ...")
        print("")

    return len(prospect_dicts)


# def find_all_prospects_not_in_prefilters(
#     parent_segment_id: int, client_sdr_id: int, print_logs: bool = True
# ):
#     # Generate the NOT LIKE conditions for titles, seniority, and locations
#     title_conditions = [
#         Prospect.title.notlike(f"%{title}%") for title in PRE_FILTERS["titles"]
#     ]
#     seniority_conditions = [
#         Prospect.title.notlike(f"%{seniority}%")
#         for seniority in PRE_FILTERS["seniority"]
#     ]
#     location_conditions = [
#         Prospect.prospect_location.notlike(f"%{location}%")
#         for location in PRE_FILTERS["location"]
#     ]

#     # Apply filters
#     prospects = (
#         Prospect.query.join(
#             ResearchPayload
#         )  # Assuming there's a one-to-one relationship
#         .filter(
#             Prospect.client_sdr_id == client_sdr_id,
#             Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
#             Prospect.segment_id == None,
#             or_(
#                 and_(*title_conditions),
#                 and_(*seniority_conditions),
#                 and_(*location_conditions),
#                 cast(
#                     func.json_extract_path_text(
#                         ResearchPayload.payload, "company", "details", "staff", "total"
#                     ),
#                     Integer,
#                 )
#                 < PRE_FILTERS["employee_count"]["min"],
#                 cast(
#                     func.json_extract_path_text(
#                         ResearchPayload.payload, "company", "details", "staff", "total"
#                     ),
#                     Integer,
#                 )
#                 > PRE_FILTERS["employee_count"]["max"],
#             ),
#         )
#         .all()
#     )

#     if print_logs:
#         print("")
#         print("### FINDING PROSPECTS NOT IN PREFILTERS ###")
#         print(
#             "Found ",
#             len(prospects),
#             " prospects who are not in the prefilter criteria ...",
#         )

#     # put all the prospects in a segment called "Z. ❌ Not in Prefilters"
#     segment: Segment = Segment(
#         segment_title="Y. ⚠️ Not in Prefilters",
#         client_sdr_id=client_sdr_id,
#         filters={},
#         parent_segment_id=parent_segment_id,
#     )
#     db.session.add(segment)
#     db.session.commit()

#     batch_size = 100
#     for i in tqdm(range(0, len(prospects), batch_size)):
#         batch_prospects = prospects[i : i + batch_size]
#         prospect_ids = [prospect.id for prospect in batch_prospects]

#         add_prospects_to_segment(
#             new_segment_id=segment.id,
#             prospect_ids=prospect_ids,
#         )

#     if print_logs:
#         print("Added ", len(prospects), " prospects to segment ...")
#         print("")

#     return prospects


def classify_contacted_prospect_campaigns(
    parent_segment_id: int,
    client_sdr_id: int,
    prospect_ids_in_segment: list[int],
    print_logs: bool = True,
):
    prospects: list[Prospect] = (
        Prospect.query.join(
            ClientArchetype, ClientArchetype.id == Prospect.archetype_id
        )
        .filter(Prospect.overall_status != ProspectOverallStatus.PROSPECTED)
        .filter_by(client_sdr_id=client_sdr_id)
        .filter(ClientArchetype.is_unassigned_contact_archetype != True)
        .with_entities(
            ClientArchetype.archetype,
            ClientArchetype.id.label("archetype_id"),
            Prospect.id,
        )
        .all()
    )

    # Filter prospect to only be the ones in the segment
    prospects = [x for x in prospects if x.id in prospect_ids_in_segment]

    if len(prospects) == 0:
        return False

    if print_logs:
        print("")
        print("### CLASSIFYING NON-PROSPECTED PROSPECTS ###")
        print(
            "Classifying ",
            len(prospects),
            " non-prospected prospects who were already sent in campaigns ...",
        )

    archetype_map: dict = {}
    # create new segment for each archetype and store in map under archetype id
    for prospect in prospects:
        archetype: str = prospect.archetype
        archetype_id: int = prospect.archetype_id

        if archetype_id in archetype_map:
            continue

        segment: Segment = Segment(
            segment_title="X. 🚀 Campaign: " + archetype,
            client_sdr_id=client_sdr_id,
            filters={},
            parent_segment_id=parent_segment_id,
        )
        db.session.add(segment)
        db.session.commit()
        archetype_map[archetype_id] = segment.id

    if print_logs:
        print("Created ", len(archetype_map), " existing campaign segments ...")

    # update prospects with segment id
    prospect_updates = []
    batch_size = 100
    for i in tqdm(range(0, len(prospects), batch_size)):
        batch_prospects = prospects[i : i + batch_size]
        for prospect in batch_prospects:
            archetype_id: int = prospect.archetype_id
            segment_id: int = archetype_map[archetype_id]
            prospect_updates.append({"id": prospect.id, "segment_id": segment_id})

        db.session.bulk_update_mappings(Prospect, prospect_updates)
        db.session.commit()
        prospect_updates = []  # Reset the list for the next batch

    if print_logs:
        print("Updated ", len(prospects), " prospects with segments ...")
        print("")

    return True


def classify_same_location_prospects(
    parent_segment_id: int,
    client_sdr_id: int,
    prospect_ids_in_segment: list[int],
    auto_filters: dict,
    print_logs: bool = True,
):
    for location in auto_filters.get("rep_location"):
        prospects: list[Prospect] = (
            Prospect.query.filter_by(client_sdr_id=client_sdr_id)
            .filter(
                Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
                Prospect.segment_id == None,
            )
            .filter(
                or_(
                    Prospect.prospect_location.like(f"%{location}%"),
                )
            )
            .all()
        )

        # Filter prospect to only be the ones in the segment
        prospects = [x for x in prospects if x.id in prospect_ids_in_segment]

        if len(prospects) == 0:
            continue

        if print_logs:
            print("")
            print("### CLASSIFYING SAME LOCATION PROSPECTS ###")
            print(
                "Classifying ",
                len(prospects),
                " prospects who are located in ",
                location,
                " ...",
            )

        segment: Segment = Segment(
            segment_title="B. 🌎 Location: " + location,
            client_sdr_id=client_sdr_id,
            filters={"location": location},
            parent_segment_id=parent_segment_id,
        )
        db.session.add(segment)
        db.session.commit()

        for prospect in prospects:
            prospect.segment_id = segment.id
        db.session.commit()

        if print_logs:
            print("Added ", len(prospects), " prospects to segment for ", location)
            print("")


def classify_same_education_prospects(
    parent_segment_id: int,
    client_sdr_id: int,
    prospect_ids_in_segment: list[int],
    auto_filters: dict,
    print_logs: bool = True,
):
    for education in auto_filters.get("rep_schools"):
        prospects: list[Prospect] = (
            Prospect.query.filter_by(client_sdr_id=client_sdr_id)
            .filter(
                Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
                Prospect.segment_id == None,
            )
            .filter(
                or_(
                    Prospect.education_1.like(f"%{education}%"),
                    Prospect.education_2.like(f"%{education}%"),
                )
            )
            .all()
        )

        # Filter prospect to only be the ones in the segment
        prospects = [x for x in prospects if x.id in prospect_ids_in_segment]

        if len(prospects) == 0:
            continue

        if print_logs:
            print("")
            print("### CLASSIFYING SAME EDUCATION PROSPECTS ###")
            print(
                "Classifying ",
                len(prospects),
                " prospects who went to ",
                education,
                " ...",
            )

        segment: Segment = Segment(
            segment_title="A. 📚 Alumni: " + education,
            client_sdr_id=client_sdr_id,
            filters={"education": education},
            parent_segment_id=parent_segment_id,
        )
        db.session.add(segment)
        db.session.commit()

        for prospect in prospects:
            prospect.segment_id = segment.id
        db.session.commit()

        if print_logs:
            print("Added ", len(prospects), " prospects to segment for ", education)
            print("")


def classify_same_former_companies_prospects(
    parent_segment_id: int,
    client_sdr_id: int,
    prospect_ids_in_segment: list[int],
    auto_filters: dict,
    print_logs: bool = True,
):
    for company in auto_filters.get("rep_former_companies"):
        prospects: list[Prospect] = (
            Prospect.query.filter_by(client_sdr_id=client_sdr_id)
            .filter(
                Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
                Prospect.segment_id == None,
            )
            .filter(
                Prospect.company == company,
            )
            .all()
        )

        # Filter prospect to only be the ones in the segment
        prospects = [x for x in prospects if x.id in prospect_ids_in_segment]

        if len(prospects) == 0:
            continue

        if print_logs:
            print("")
            print("### CLASSIFYING SAME FORMER COMPANIES PROSPECTS ###")
            print(
                "Classifying ",
                len(prospects),
                " prospects who worked at ",
                company,
                " ...",
            )

        segment: Segment = Segment(
            segment_title="C. 💼 Former Company: " + company,
            client_sdr_id=client_sdr_id,
            filters={"former_company": company},
            parent_segment_id=parent_segment_id,
        )
        db.session.add(segment)
        db.session.commit()

        for prospect in prospects:
            prospect.segment_id = segment.id
        db.session.commit()

        if print_logs:
            print("Added ", len(prospects), " prospects to segment for ", company)
            print("")


# def classify_same_industry_prospects(client_sdr_id: int, print_logs: bool = True):
#     for industry in PROSPECT_INDUSTRIES:
#         prospects: list[Prospect] = (
#             Prospect.query.filter_by(client_sdr_id=client_sdr_id)
#             .filter(
#                 Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
#                 Prospect.segment_id == None,
#             )
#             .filter(
#                 Prospect.industry.like(f"%{industry}%"),
#             )
#             .all()
#         )

#         if len(prospects) == 0:
#             continue

#         if print_logs:
#             print("")
#             print("### CLASSIFYING SAME INDUSTRY PROSPECTS ###")
#             print(
#                 "Classifying ",
#                 len(prospects),
#                 " prospects who are in the ",
#                 industry,
#                 " industry ...",
#             )

#         segment: Segment = Segment(
#             segment_title="D. 🏭 Industry: " + industry,
#             client_sdr_id=client_sdr_id,
#             filters={"industry": industry},
#             parent_segment_id=parent_segment_id,
#         )
#         db.session.add(segment)
#         db.session.commit()

#         batch_size = 100
#         for i in range(0, len(prospects), batch_size):
#             batch = prospects[i : i + batch_size]
#             prospect_ids = [prospect.id for prospect in batch]

#             stmt = (
#                 update(Prospect)
#                 .where(Prospect.id.in_(prospect_ids))
#                 .values(segment_id=segment.id)
#             )
#             db.session.execute(stmt)
#             db.session.commit()

#         if print_logs:
#             print("Added ", len(prospects), " prospects to segment for ", industry)
#             print("")


def classify_same_title_industry_prospects(
    parent_segment_id: int,
    client_sdr_id: int,
    prospect_ids_in_segment: list[int],
    auto_filters: dict,
    print_logs: bool = True,
):
    for industry in auto_filters.get("prospect_industries"):
        for titles in auto_filters.get("prospect_titles"):
            prospects: list[Prospect] = (
                Prospect.query.filter_by(client_sdr_id=client_sdr_id)
                .filter(
                    Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
                    Prospect.segment_id == None,
                )
                .filter(
                    Prospect.industry.like(f"%{industry}%"),
                    or_(
                        *[Prospect.title.like(f"%{title}%") for title in titles],
                    ),
                )
                .all()
            )

            # Filter prospect to only be the ones in the segment
            prospects = [x for x in prospects if x.id in prospect_ids_in_segment]

            if len(prospects) == 0:
                continue

            if print_logs:
                print("")
                print("### CLASSIFYING SAME TITLE INDUSTRY PROSPECTS ###")
                print(
                    "Classifying ",
                    len(prospects),
                    " prospects who are in the ",
                    industry,
                    " industry and have titles ",
                    titles,
                    " ...",
                )

            sample_titles = ", ".join(titles[:3])
            segment: Segment = Segment(
                segment_title="D. 🏭 Industry: " + industry + " - " + sample_titles,
                client_sdr_id=client_sdr_id,
                filters={"industry": industry, "title": titles},
                parent_segment_id=parent_segment_id,
            )
            db.session.add(segment)
            db.session.commit()

            batch_size = 100
            for i in range(0, len(prospects), batch_size):
                batch = prospects[i : i + batch_size]
                prospect_ids = [prospect.id for prospect in batch]

                stmt = (
                    update(Prospect)
                    .where(Prospect.id.in_(prospect_ids))
                    .values(segment_id=segment.id)
                )
                db.session.execute(stmt)
                db.session.commit()

            if print_logs:
                print(
                    "Added ",
                    len(prospects),
                    " prospects to segment for ",
                    titles,
                    " in ",
                    industry,
                )
                print("")


def classify_same_company_size_prospects(
    parent_segment_id: int,
    client_sdr_id: int,
    prospect_ids_in_segment: list[int],
    auto_filters: dict,
    print_logs: bool = True,
):
    for company_size in auto_filters.get("prospect_company_size_map"):
        prospects = (
            Prospect.query.join(
                ResearchPayload
            )  # Assuming there's a one-to-one relationship
            .filter(
                Prospect.client_sdr_id == client_sdr_id,
                Prospect.overall_status == ProspectOverallStatus.PROSPECTED,
                Prospect.segment_id == None,
                Prospect.company_size >= company_size["min"],
                Prospect.company_size <= company_size["max"],
            )
            .all()
        )

        # Filter prospect to only be the ones in the segment
        prospects = [x for x in prospects if x.id in prospect_ids_in_segment]

        if len(prospects) == 0:
            continue

        if print_logs:
            print("")
            print("### CLASSIFYING SAME COMPANY SIZE PROSPECTS ###")
            print(
                "Classifying ",
                len(prospects),
                " prospects who are in the ",
                company_size["label"],
                " company size ...",
            )

        segment: Segment = Segment(
            segment_title="E. 🏢 Company Size: " + company_size["label"],
            client_sdr_id=client_sdr_id,
            filters={"company_size": company_size},
            parent_segment_id=parent_segment_id,
        )
        db.session.add(segment)
        db.session.commit()

        batch_size = 100
        for i in range(0, len(prospects), batch_size):
            batch = prospects[i : i + batch_size]
            prospect_ids = [prospect.id for prospect in batch]

            stmt = (
                update(Prospect)
                .where(Prospect.id.in_(prospect_ids))
                .values(segment_id=segment.id)
            )
            db.session.execute(stmt)
            db.session.commit()

        if print_logs:
            print(
                "Added ",
                len(prospects),
                " prospects to segment for ",
                company_size["label"],
            )
            print("")


def prune_small_segments(client_sdr_id: int, segment_id: int, print_logs: bool = True):
    # If a segment has less than MIN_PROSPECTS prospects, delete it
    MIN_PROSPECTS = 20

    segments: list[Segment] = Segment.query.filter_by(
        parent_segment_id=segment_id
    ).all()

    for segment in segments:
        prospect_ids = get_prospect_ids_for_segment(segment.id)
        if len(prospect_ids) < MIN_PROSPECTS:
            if print_logs:
                print("Pruning small segment: ", segment.segment_title)
            wipe_and_delete_segment(client_sdr_id=client_sdr_id, segment_id=segment.id)
            db.session.commit()


def run_auto_segment(segment_id: int, auto_filters: dict):

    # rep_schools: list = ["University of California, Santa Cruz"]
    # rep_location: list = ["San Francisco"]
    # rep_former_companies: list = ["Retool", "Infor"]
    # prospect_industries: list = [
    #     "Computer Software",
    # ]
    # prospect_titles: list = [
    #     [
    #         "CEO", "CTO", "CFO", "COO", "CIO", "VP",
    #     ],
    #     ["Manager", "Director", "Project Manager"],
    #     ["Analyst"]
    # ]
    prospect_company_size_map: list = [
        {"min": 0, "max": 50, "label": "Startup"},
        {"min": 50, "max": 1000, "label": "Mid Market"},
        {"min": 1000, "max": 10000000, "label": "Enterprise"},
    ]

    auto_filters = {
        **auto_filters,
        "prospect_company_size_map": prospect_company_size_map,
    }

    # Get the segment

    segment: Segment = Segment.query.get(segment_id)

    client_sdr: ClientSDR = ClientSDR.query.get(segment.client_sdr_id)
    client_sdr_name: str = client_sdr.name
    print("Running autosegment for:", client_sdr_name)

    prospect_ids_in_segment = get_prospect_ids_for_segment(segment_id)

    wipe_segment_ids_from_prospects_in_segment(segment_id)

    print("Do Not Contact Segment")
    find_all_do_not_contact_prospects(
        parent_segment_id=segment_id,
        client_sdr_id=segment.client_sdr_id,
        prospect_ids_in_segment=prospect_ids_in_segment,
    )

    print("Contacted Prospects Segment")
    classify_contacted_prospect_campaigns(
        parent_segment_id=segment_id,
        client_sdr_id=segment.client_sdr_id,
        prospect_ids_in_segment=prospect_ids_in_segment,
    )

    print("Same Education Segment")
    classify_same_education_prospects(
        parent_segment_id=segment_id,
        client_sdr_id=segment.client_sdr_id,
        prospect_ids_in_segment=prospect_ids_in_segment,
        auto_filters=auto_filters,
    )

    print("Same Location Segment")
    classify_same_location_prospects(
        parent_segment_id=segment_id,
        client_sdr_id=segment.client_sdr_id,
        prospect_ids_in_segment=prospect_ids_in_segment,
        auto_filters=auto_filters,
    )

    print("Same Former Companies Segment")
    classify_same_former_companies_prospects(
        parent_segment_id=segment_id,
        client_sdr_id=segment.client_sdr_id,
        prospect_ids_in_segment=prospect_ids_in_segment,
        auto_filters=auto_filters,
    )

    print("Same Title Industry Segment")
    classify_same_title_industry_prospects(
        parent_segment_id=segment_id,
        client_sdr_id=segment.client_sdr_id,
        prospect_ids_in_segment=prospect_ids_in_segment,
        auto_filters=auto_filters,
    )

    print("Same Company Size Segment")
    classify_same_company_size_prospects(
        parent_segment_id=segment_id,
        client_sdr_id=segment.client_sdr_id,
        prospect_ids_in_segment=prospect_ids_in_segment,
        auto_filters=auto_filters,
    )

    # print("Pruning Small Segments")
    # prune_small_segments(client_sdr_id=segment.client_sdr_id, segment_id=segment_id)

    return True
