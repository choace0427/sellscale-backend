from app import db
from model_import import ResearchPointType, ClientArchetype
from typing import Union


def update_transformer_blocklist(client_archetype_id: int, new_blocklist: list) -> any:
    """
    Set's the client archetype'ss transformer blocker

    Args:
        client_archetype_id (int): Client Archetype ID
        new_blocklist (list): New block list to use for client archetype

    Returns:
        tuple[bool, str]: success & message
    """
    for item in new_blocklist:
        if not ResearchPointType.has_value(item):
            return False, "Invalid research point type found: {}".format(item)

    ca: ClientArchetype = ClientArchetype.query.get(client_archetype_id)
    if not ca:
        return False, "Client archetype not found"

    ca.transformer_blocklist = new_blocklist
    db.session.add(ca)
    db.session.commit()

    return True, "OK"


def replicate_transformer_blocklist(
    source_client_archetype_id: int, destination_client_archetype_id: int
) -> any:
    """Replicates the source client archetype's transformer blocklist to destination client archetype

    Args:
        source_client_archetype_id (int): id of client archetype to copy
        destination_client_archetype_id (int): id of client archetype to paste to

    Returns:
        tuple[bool, str]: success & message
    """
    source_ca: ClientArchetype = ClientArchetype.query.get(source_client_archetype_id)
    if not source_ca:
        return False, "Source client archetype not found"
    destination_ca: ClientArchetype = ClientArchetype.query.get(
        destination_client_archetype_id
    )
    if not destination_ca:
        return False, "Destination client archetype not found"

    destination_ca.transformer_blocklist = source_ca.transformer_blocklist
    db.session.add(destination_ca)
    db.session.commit()

    return True, "OK"


def get_archetype_details_for_sdr(client_sdr_id: int):
    """
    Given a client sdr id, return the archetype details.

    Details look like so:
    [
        {
            id: (int) client archetype id,
            name: (str) client archetype name,
            active: (bool) if the client archetype is active,
            num_prospects: (int) number of prospects with this archetype
            num_unused_li_prospects: (int) number of prospects with this archetype that are unused LI prospects
            num_unused_email_prospects: (int) number of prospects with this archetype that are unused email prospects
            percent_unused_li_prospects: (float) percent of prospects with this archetype that are unused LI prospects
            percent_unused_email_prospects: (float) percent of prospects with this archetype that are unused email prospects
        },
        ...
    ]
    """

    query = """
        select 
            client_archetype.id,
            client_archetype.archetype "name",
            client_archetype.active,
            count(distinct prospect.id) "num_prospects",
            count(distinct prospect.id) filter (where prospect.approved_outreach_message_id is null) "num_unused_li_prospects",
            count(distinct prospect.id) filter (where prospect.approved_prospect_email_id is null)"num_unused_email_prospects",
            cast(count(distinct prospect.id) filter (where prospect.approved_outreach_message_id is null) as float) / count(distinct prospect.id) "percent_unused_li_prospects",
            cast(count(distinct prospect.id) filter (where prospect.approved_prospect_email_id is null) as float) / count(distinct prospect.id) "percent_unused_li_prospects"
        from client_archetype
            join prospect on prospect.archetype_id = client_archetype.id
        where client_archetype.client_sdr_id = {client_sdr_id}
        group by 1,2,3
        order by active desc, archetype desc;
    """.format(
        client_sdr_id=client_sdr_id
    )

    data = db.session.execute(query).fetchall()
    list_of_archetypes = []
    for entry in data:
        list_of_archetypes.append(
            {
                "id": entry[0],
                "name": entry[1],
                "active": entry[2],
                "num_prospects": entry[3],
                "num_unused_li_prospects": entry[4],
                "num_unused_email_prospects": entry[5],
                "percent_unused_li_prospects": entry[6],
                "percent_unused_email_prospects": entry[7],
            }
        )

    return list_of_archetypes
