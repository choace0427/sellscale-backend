import datetime
from typing import List, Optional, Tuple

from src.utils.slack import send_slack_message, URL_MAP

from src.client.models import ClientArchetype, ClientSDR
from src.smartlead.smartlead import Smartlead, EmailWarming

from app import db, celery

def get_all_email_warmings(sdr_name: str) -> list[EmailWarming]:
  
  sl = Smartlead()
  emails = sl.get_emails()
  
  warmings = []
  for email in emails:
    if sdr_name != email.get("from_name"): continue
    
    warmup_stats = sl.get_warmup_stats(email.get("id"))
    warming = EmailWarming(
      id=email.get("id"),
      name=email.get("from_name"),
      email=email.get("from_email"),
      status=email.get("warmup_details", {}).get("status"),
      total_sent=email.get("warmup_details", {}).get("total_sent_count"),
      total_spam=email.get("warmup_details", {}).get("total_spam_count"),
      warmup_reputation=email.get("warmup_details", {}).get("warmup_reputation"),
      
      sent_count=warmup_stats.get("sent_count"),
      spam_count=warmup_stats.get("spam_count"),
      inbox_count=warmup_stats.get("inbox_count"),
      warmup_email_received_count=warmup_stats.get("warmup_email_received_count"),
      stats_by_date=warmup_stats.get("stats_by_date"),
      percent_complete=get_warmup_percentage(int(warmup_stats.get("sent_count")))
    )
    warmings.append(warming)
  
  return warmings


def get_email_warmings_for_sdr(client_sdr_id: int) -> list[EmailWarming]:
  
  sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
  if sdr.meta_data:
      old_warmings = sdr.meta_data.get("email_warmings", [])
  else:
      old_warmings = []
  
  warmings: list[EmailWarming] = get_all_email_warmings(sdr.name)
      
  for warming in warmings:
    for old_warming in old_warmings:
      if warming.id == old_warming.get("id"):
        
        # Finished warming
        if warming.percent_complete == 100 and old_warming.get('percent_complete') != 100:
          send_slack_message(
              message="🔥 Domain warmed",
              blocks=[
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": f"🔥 *Domain warmed -* `{warming.email}`"
                  }
                },
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": f">_A SellScale AI domain has finished warming. It may now be used to send up to 40 emails/day._"
                  }
                }
              ],
              webhook_urls=[URL_MAP["ops-outbound-warming"]],
          )
  
  if sdr.meta_data:
      sdr.meta_data["email_warmings"] = [warming.to_dict() for warming in warmings]
  else:
      sdr.meta_data = {"email_warmings": [warming.to_dict() for warming in warmings]}
  db.session.commit()
      
  return warmings
  

def get_warmup_percentage(sent_count: int) -> int:
    TOTAL_SENT = 160
  
    return min(round((sent_count / TOTAL_SENT) * 100, 0), 100)

# def get_warmup_percentage(warming_stats_by_date: list) -> int:
#     WARMUP_LENGTH = 14
  
#     first = warming_stats_by_date[0]
#     # last = warming_stats_by_date[-1]
    
#     # Convert date strings to datetime objects
#     date_first = datetime.datetime.strptime(first.get('date'), '%Y-%m-%d')
#     date_last = datetime.datetime.utcnow() #.strptime(last.get('date'), '%Y-%m-%d')

#     # Calculate the difference between the two dates
#     date_difference = date_last - date_first

#     return min(round((date_difference.days / WARMUP_LENGTH) * 100, 0), 100)
  

def sync_campaign_analytics(client_sdr_id: int) -> bool:
  
    archetypes: list[ClientArchetype] = ClientArchetype.query.filter(
        ClientArchetype.client_sdr_id == client_sdr_id,
    ).all()
    
    for archetype in archetypes:
        if(archetype.smartlead_campaign_id == None): continue
      
        # if archetype.meta_data:
        #     analytics = archetype.meta_data.get("smartlead_campaign_analytics", {})
        # else:
        #     analytics = {}
        
        sl = Smartlead()
        analytics = sl.get_campaign_analytics(archetype.smartlead_campaign_id)
        
        if archetype.meta_data:
            archetype.meta_data["smartlead_campaign_analytics"] = analytics
        else:
            archetype.meta_data = {"smartlead_campaign_analytics": analytics}
        db.session.commit()
        
    
def set_campaign_id(archetype_id: int, campaign_id: int) -> bool:
  
    archetype: ClientArchetype = ClientArchetype.query.get(archetype_id)
    archetype.smartlead_campaign_id = campaign_id
    db.session.commit()
    
    return True
    
    