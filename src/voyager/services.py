import json
import datetime as dt
from src.li_conversation.services import create_linkedin_conversation_entry
from model_import import ClientSDR
from app import db
from tqdm import tqdm
from src.utils.abstract.attr_utils import deep_get
from src.voyager.linkedin import Linkedin

def update_linked_cookies(client_sdr_id: int, cookies: str):
    """ Updates LinkedIn cookies for Voyager

    Args:
        client_sdr_id (int): ID of the client SDR
        cookies (str): LinkedIn cookies

    Returns:
        status_code (int), message (str): HTTP status code 
    """
    
    sdr: ClientSDR = ClientSDR.query.filter(ClientSDR.id == client_sdr_id).first()
    if not sdr:
        return "No client sdr found with this id", 400 

    sdr.li_at_token = json.loads(cookies).get("li_at")
    sdr.li_cookies = cookies

    db.session.add(sdr)
    db.session.commit()

    return "Updated cookies", 200


def update_conversation_entries(client_sdr_id: int, target_urn_id: str):
    """ Updates LinkedinConversationEntry table with new entries

    Args:
        client_sdr_id (int): ID of the client SDR
        target_urn_id (str): LinkedIn profile URN id

    Returns:
        status_code (int), message (str): HTTP status code 
    """

    api = Linkedin(client_sdr_id)

    details = api.get_conversation_details(target_urn_id)
    if not details:
      return "No conversation found with this public id", 400
    convo = api.get_conversation(details['entityUrn'].replace('urn:li:fs_conversation:', ''))

    bulk_objects = []
    for message in tqdm(convo['elements']):

        first_name = message.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("firstName", "")
        last_name = message.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("lastName", "")
        urn_id = public_id = message.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("entityUrn", "").replace("urn:li:fs_miniProfile:", "")
        public_id = message.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("publicIdentifier", "")
        headline = message.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("occupation", "")

        msg = message.get("eventContent", {}).get("com.linkedin.voyager.messaging.event.MessageEvent", {}).get("attributedBody", {}).get("text", "")

        bulk_objects.append(
            create_linkedin_conversation_entry(
                conversation_url="https://www.linkedin.com/messaging/thread/{value}/".format(value=message.get("entityUrn", "").replace("urn:li:fs_event:(", "").split(",")[0]),
                author=first_name+' '+last_name,
                first_name=first_name,
                last_name=last_name,
                date=dt.datetime.utcfromtimestamp(message.get("createdAt", 0)/1000),
                profile_url="https://www.linkedin.com/in/{value}/".format(value=urn_id),
                headline=headline,
                img_url="",
                connection_degree='1st' if urn_id == target_urn_id else 'You',
                li_url="https://www.linkedin.com/in/{value}/".format(value=public_id),
                message=msg,
            )
        )
    print("saving objects ...")
    bulk_objects = [obj for obj in bulk_objects if obj]
    db.session.bulk_save_objects(bulk_objects)
    db.session.commit()
    print("Done saving!")

    return "OK", 200
