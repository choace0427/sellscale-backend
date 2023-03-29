import json
import datetime as dt

from src.research.models import IScraperPayloadCache
from src.prospecting.models import Prospect
from src.li_conversation.services import create_linkedin_conversation_entry
from model_import import ClientSDR
from app import db
from tqdm import tqdm
from src.utils.abstract.attr_utils import deep_get
from src.voyager.linkedin import Linkedin

def get_profile_urn_id(prospect_id: int):
  """ Gets the URN ID of a prospect, saving the URN ID if it's not already saved

    Args:
        prospect_id (int): ID of the prospect

    Returns:
        li_urn_id (str) or None: LinkedIn URN ID
    """

  prospect: Prospect = Prospect.query.get(prospect_id)

  if not prospect:
    return None
  if prospect.li_urn_id:
    return str(prospect.li_urn_id)
  
  # If we don't have the URN ID, we get one from the iscraper data
  iscraper_data: IScraperPayloadCache = IScraperPayloadCache.get_iscraper_payload_cache_by_linkedin_url(prospect.linkedin_url)
  if iscraper_data:
    personal_info = json.loads(iscraper_data.payload)
    urn_id = personal_info.get("entity_urn", None)
    if urn_id:
      prospect.li_urn_id = urn_id
      db.session.add(prospect)
      db.session.commit()
      return str(urn_id)
  
  return None


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


def update_conversation_entries(api: Linkedin, convo_urn_id: str):
    """ Updates LinkedinConversationEntry table with new entries

    Args:
        api (LinkedIn): instance of LinkedIn class
        convo_urn_id (str): LinkedIn convo URN id

    Returns:
        status_code (int), message (str): HTTP status code 
    """

    convo = api.get_conversation(convo_urn_id)

    if not convo or not convo.get('elements'):
      return "No conversation found", 400

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
                # TODO: This should be based on a profile id instead of the name
                connection_degree='You' if api.is_profile(first_name, last_name) else '1st',
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
