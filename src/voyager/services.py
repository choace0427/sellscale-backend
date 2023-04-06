import json
import time
import datetime as dt

from src.li_conversation.models import LinkedinConversationEntry
from src.research.models import IScraperPayloadCache
from src.prospecting.models import Prospect
from typing import Union
from src.li_conversation.services import create_linkedin_conversation_entry
from model_import import ClientSDR
from app import db
from tqdm import tqdm
from src.utils.abstract.attr_utils import deep_get
from src.voyager.linkedin import LinkedIn

def get_profile_urn_id(prospect_id: int, api: Union[LinkedIn, None] = None):
  """ Gets the URN ID of a prospect, saving the URN ID if it's not already saved

    Args:
        prospect_id (int): ID of the prospect
        client_sdr_id (int): Optional - ID of the client SDR

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
  
  # If we still don't have the URN ID, we get one from Voyager using the public id
  if api and prospect.linkedin_url:
    public_id = prospect.linkedin_url.split("/in/")[1].split("/")[0]
    if public_id:
      profile = api.get_profile(public_id)
      urn_id = profile.get("profile_id", None) if profile else None
      if urn_id:
        prospect.li_urn_id = urn_id
        db.session.add(prospect)
        db.session.commit()
        return str(urn_id)

  return None


def update_linkedin_cookies(client_sdr_id: int, cookies: str):
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

def clear_linkedin_cookies(client_sdr_id: int):
    """ Clears LinkedIn cookies for Voyager

    Args:
        client_sdr_id (int): ID of the client SDR

    Returns:
        status_code (int), message (str): HTTP status code 
    """
    
    sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
    if not sdr:
        return "No client sdr found with this id", 400 

    sdr.li_cookies = None

    db.session.add(sdr)
    db.session.commit()

    return "Cleared cookies", 200


def fetch_conversation(api: LinkedIn, prospect_id: int, check_for_update: bool = True):
    """ Gets the latest conversation with a prospect, syncing the db as needed

    Args:
        api (LinkedIN): instance of LinkedIn class
        prospect_id (int): ID of the prospect
        check_for_update (bool): Optional - Whether to check for new messages from LinkedIn

    Returns:
        convo_entries (LinkedinConversationEntry[]): List of conversation entries
    """

    # Utility function for getting db conversation entries to json
    def get_convo_entries(convo_urn_id: str) -> list[str]:
      return [e.to_dict() for e in LinkedinConversationEntry.query.filter_by(
        conversation_url=f'https://www.linkedin.com/messaging/thread/{convo_urn_id}/'
      ).order_by(LinkedinConversationEntry.date.desc()).all()]

    prospect_urn_id = get_profile_urn_id(prospect_id, api)

    # Check if we need to update the conversation 
    details = api.get_conversation_details(prospect_urn_id)
    if not details:
      return []
    convo_urn_id = details['id']
    last_msg_urn_id = details['events'][0]['dashEntityUrn'].replace("urn:li:fsd_message:", "")
    convo_entry = LinkedinConversationEntry.query.filter_by(urn_id=last_msg_urn_id).first()

    prospect: Prospect = Prospect.query.get(prospect_id)

    # If the prospect's profile img is expired, update it
    if time.time()*1000 > int(prospect.img_expire):
      prospect.img_url = details.get("participants", [])[0].get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("rootUrl", "")+details.get("participants", [])[0].get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("artifacts", [])[2].get("fileIdentifyingUrlPathSegment", "")
      prospect.img_expire = details.get("participants", [])[0].get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("artifacts", [])[2].get("expiresAt", 0)
      db.session.add(prospect)
      db.session.commit()
    # If the SDR's profile img is expired, update it
    if time.time()*1000 > int(api.client_sdr.img_expire):
      api.client_sdr.img_url = details.get("events", [])[0].get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("rootUrl", "")+details.get("events", [])[0].get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("artifacts", [])[2].get("fileIdentifyingUrlPathSegment", "")
      api.client_sdr.img_expire = details.get("events", [])[0].get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("artifacts", [])[2].get("expiresAt", 0)
      db.session.add(api.client_sdr)
      db.session.commit()

    # If li_conversation_thread_id not set, might as well save it now
    if not prospect.li_conversation_thread_id:
      prospect.li_conversation_thread_id = f'https://www.linkedin.com/messaging/thread/{convo_urn_id}/'
      db.session.add(prospect)
      db.session.commit()

    # If not, we return the conversation from the database
    if convo_entry or not check_for_update:
      return get_convo_entries(convo_urn_id)
    else:
      # If we need to update the conversation, we do so
      update_conversation_entries(api, convo_urn_id)
      return get_convo_entries(convo_urn_id)


def update_conversation_entries(api: LinkedIn, convo_urn_id: str):
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
        image_url = message.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("rootUrl", "")+message.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("artifacts", [])[2].get("fileIdentifyingUrlPathSegment", "")
        image_expire = message.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("picture", {}).get("com.linkedin.common.VectorImage", {}).get("artifacts", [])[2].get("expiresAt", 0)
        msg_urn_id = message.get('dashEntityUrn', "").replace("urn:li:fsd_message:", "")

        msg = message.get("eventContent", {}).get("com.linkedin.voyager.messaging.event.MessageEvent", {}).get("attributedBody", {}).get("text", "")
        connection_degree = 'You' if api.is_profile(first_name, last_name) else '1st'

        bulk_objects.append(
            create_linkedin_conversation_entry(
                conversation_url="https://www.linkedin.com/messaging/thread/{value}/".format(value=message.get("entityUrn", "").replace("urn:li:fs_event:(", "").split(",")[0]),
                author=first_name+' '+last_name,
                first_name=first_name,
                last_name=last_name,
                date=dt.datetime.utcfromtimestamp(message.get("createdAt", 0)/1000),
                profile_url="https://www.linkedin.com/in/{value}/".format(value=urn_id),
                headline=headline,
                img_url=image_url,
                img_expire=image_expire,
                # TODO: This should be based on a profile id instead of the name
                connection_degree=connection_degree,
                li_url="https://www.linkedin.com/in/{value}/".format(value=public_id),
                message=msg,
                urn_id=msg_urn_id,
            )
        )
    print("saving objects ...")
    bulk_objects = [obj for obj in bulk_objects if obj]
    db.session.bulk_save_objects(bulk_objects)
    db.session.commit()
    print("Done saving!")

    return "OK", 200
