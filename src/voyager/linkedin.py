"""
Provides linkedin api-related code
"""
import base64
import math
from typing import Optional
import urllib.parse
import json
import logging
import random
import uuid
from operator import itemgetter
from time import sleep, time
from urllib.parse import quote, urlencode
from flask import Response, jsonify, make_response
from src.voyager.hackathon_services import make_search
from app import db
from sqlalchemy.orm import Session
from src.utils.slack import send_slack_message, URL_MAP
from requests.cookies import cookiejar_from_dict

from requests import TooManyRedirects

from src.client.models import ClientSDR
from src.voyager.client import Client
from src.voyager.utils.helpers import (
    append_update_post_field_to_posts_list,
    get_id_from_urn,
    get_list_posts_sorted_without_promoted,
    get_update_author_name,
    get_update_author_profile,
    get_update_content,
    get_update_old,
    get_update_url,
    parse_list_raw_posts,
    parse_list_raw_urns,
    generate_trackingId,
    generate_trackingId_as_charString,
)

logger = logging.getLogger(__name__)


def default_evade(request_count: int):
    """
    A catch-all method to try and evade suspension from Linkedin.
    Currenly, just delays the request by a random (bounded) time
    """
    if request_count == 1:
        return
    else:
        sleep(
            random.uniform(0.01, 0.90)
        )  # sleep a random duration to try and evade suspention


class LinkedIn(object):
    """
    Class for accessing the LinkedIn API.
    :param username: Username of LinkedIn account.
    :type username: str
    :param password: Password of LinkedIn account.
    :type password: str
    """

    _MAX_POST_COUNT = 100  # max seems to be 100 posts per page
    _MAX_UPDATE_COUNT = 100  # max seems to be 100
    _MAX_SEARCH_COUNT = 49  # max seems to be 49, and min seems to be 2
    _MAX_REPEATED_REQUESTS = (
        200  # VERY conservative max requests count to avoid rate-limit
    )

    def __init__(
        self,
        client_sdr_id,
        *,
        authenticate=True,
        refresh_cookies=False,
        debug=False,
        proxies={},
        cookies=None,
    ):
        """Constructor method"""
        self.client = Client(
            refresh_cookies=refresh_cookies,
            debug=debug,
            proxies=proxies,
        )
        self.request_count = 0  # number of requests made to linkedin

        logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
        self.logger = logger

        self.client_sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        self.client_sdr_id = client_sdr_id

        if authenticate:
            if cookies:
                # If the cookies are expired, the API won't work anymore since
                # `username` and `password` are not used at all in this case.
                cookies = cookiejar_from_dict(json.loads(cookies))
                self.client._set_session_cookies(cookies)
            else:
                self.client.authenticate(self.client_sdr)

    def _fetch(self, uri, evade=default_evade, base_request=False, **kwargs):
        """GET request to Linkedin API"""
        self.request_count += 1
        evade(self.request_count)

        url = f"{self.client.API_BASE_URL if not base_request else self.client.LINKEDIN_BASE_URL}{uri}"
        try:
            res = self.client.session.get(url, **kwargs)

            send_slack_message(
                message=f"<{self.client_sdr_id}> Get response: {str(res)}\n\n {res.raw}\n\n {res.reason}\n\n {res.__dict__}\n\n {res.text}",
                webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
            )

            if res.status_code == 401:
                raise Exception("Invalid cookies")

            # Attempt request again if we're being rate limited
            if res.status_code == 400 and self.request_count < 20:
                return self._fetch(uri=uri, base_request=base_request, **kwargs)

            return res
        except Exception as e:
            
            send_slack_message(
                message=f"<{self.client_sdr_id}> Error on fetch, {str(e)}",
                webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
            )

            sdr: ClientSDR = ClientSDR.query.get(self.client_sdr.id)
            if sdr:

                if sdr.li_cookies != "INVALID":
                    send_slack_message(
                        message=f"SDR {sdr.name} (#{sdr.id})'s LinkedIn cookie is now invalid! It needs to be resynced.",
                        webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
                    )

                sdr.li_cookies = "INVALID"
                db.session.add(sdr)
                db.session.commit()
            return None

    def _post(self, uri, evade=default_evade, base_request=False, **kwargs):
        """POST request to Linkedin API"""
        self.request_count += 1
        evade(self.request_count)

        url = f"{self.client.API_BASE_URL if not base_request else self.client.LINKEDIN_BASE_URL}{uri}"
        try:
            res = self.client.session.post(url, **kwargs)

            send_slack_message(
                message=f"<{self.client_sdr_id}> Post response: {str(res)}\n\n {res.raw}\n\n {res.reason}\n\n {res.__dict__}\n\n {res.text}",
                webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
            )

            if res.status_code == 401:
                raise Exception("Invalid cookies")

            # Attempt request again if we're being rate limited
            if res.status_code == 400 and self.request_count < 20:
                return self._post(uri=uri, base_request=base_request, **kwargs)

            return res
        except Exception as e:
            
            send_slack_message(
                message=f"<{self.client_sdr_id}> Error on post, {str(e)}",
                webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
            )

            sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
            if sdr:

                if sdr.li_cookies != "INVALID":
                    send_slack_message(
                        message=f"SDR {sdr.name} (#{sdr.id})'s LinkedIn cookie is now invalid! It needs to be resynced.",
                        webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
                    )

                sdr.li_cookies = "INVALID"
                db.session.add(sdr)
                db.session.commit()
            return None

    def is_valid(self):
        """Checks if the client SDR is valid"""
        client_sdr: ClientSDR = ClientSDR.query.get(self.client_sdr_id)
        if client_sdr:
            return client_sdr.li_cookies != "INVALID"
        else:
            return False

    def get_profile(self, public_id=None, urn_id=None):
        """Fetch data for a given LinkedIn profile.
        :param public_id: LinkedIn public ID for a profile
        :type public_id: str, optional
        :param urn_id: LinkedIn URN ID for a profile
        :type urn_id: str, optional
        :return: Profile data
        :rtype: dict
        """
        # TODO: this still works for now, but will probably eventually have to be converted to
        # https://www.linkedin.com/voyager/api/identity/profiles/ACoAAAKT9JQBsH7LwKaE9Myay9WcX8OVGuDq9Uw
        res = self._fetch(f"/identity/profiles/{public_id or urn_id}/profileView")
        if res.status_code == 403:
            sdr = self.client_sdr
            send_slack_message(
                message=f"SDR {sdr.name} (#{sdr.id}) returned a 403 response from LinkedIn. Investigate?",
                webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
            )
            return None
        if res is None:
            return None

        data = res.json()
        if data and "status" in data and data["status"] != 200:
            self.logger.info("request failed: {}".format(data["message"]))
            return {}

        # massage [profile] data
        profile = data["profile"]
        if "miniProfile" in profile:
            if "picture" in profile["miniProfile"]:
                profile["displayPictureUrl"] = profile["miniProfile"]["picture"][
                    "com.linkedin.common.VectorImage"
                ]["rootUrl"]

                images_data = profile["miniProfile"]["picture"][
                    "com.linkedin.common.VectorImage"
                ]["artifacts"]
                for img in images_data:
                    w, h, url_segment = itemgetter(
                        "width", "height", "fileIdentifyingUrlPathSegment"
                    )(img)
                    profile[f"img_{w}_{h}"] = url_segment

            profile["profile_id"] = get_id_from_urn(profile["miniProfile"]["entityUrn"])
            profile["profile_urn"] = profile["miniProfile"]["entityUrn"]
            profile["member_urn"] = profile["miniProfile"]["objectUrn"]
            profile["public_id"] = profile["miniProfile"]["publicIdentifier"]

            del profile["miniProfile"]

        del profile["defaultLocale"]
        del profile["supportedLocales"]
        del profile["versionTag"]
        del profile["showEducationOnProfileTopCard"]

        # massage [experience] data
        experience = data["positionView"]["elements"]
        for item in experience:
            if "company" in item and "miniCompany" in item["company"]:
                if "logo" in item["company"]["miniCompany"]:
                    logo = item["company"]["miniCompany"]["logo"].get(
                        "com.linkedin.common.VectorImage"
                    )
                    if logo:
                        item["companyLogoUrl"] = logo["rootUrl"]
                del item["company"]["miniCompany"]

        profile["experience"] = experience

        # massage [education] data
        education = data["educationView"]["elements"]
        for item in education:
            if "school" in item:
                if "logo" in item["school"]:
                    item["school"]["logoUrl"] = item["school"]["logo"][
                        "com.linkedin.common.VectorImage"
                    ]["rootUrl"]
                    del item["school"]["logo"]

        profile["education"] = education

        # massage [languages] data
        languages = data["languageView"]["elements"]
        for item in languages:
            del item["entityUrn"]
        profile["languages"] = languages

        # massage [publications] data
        publications = data["publicationView"]["elements"]
        for item in publications:
            del item["entityUrn"]
            for author in item.get("authors", []):
                del author["entityUrn"]
        profile["publications"] = publications

        # massage [certifications] data
        certifications = data["certificationView"]["elements"]
        for item in certifications:
            del item["entityUrn"]
        profile["certifications"] = certifications

        # massage [volunteer] data
        volunteer = data["volunteerExperienceView"]["elements"]
        for item in volunteer:
            del item["entityUrn"]
        profile["volunteer"] = volunteer

        # massage [honors] data
        honors = data["honorView"]["elements"]
        for item in honors:
            del item["entityUrn"]
        profile["honors"] = honors

        # massage [projects] data
        projects = data["projectView"]["elements"]
        for item in projects:
            del item["entityUrn"]
        profile["projects"] = projects

        return profile


    def remove_connection(self, public_profile_id, invite_urn_id):
        """Remove a given profile as a connection.

        :param public_profile_id: public ID of a LinkedIn profile
        :type public_profile_id: str

        :return: Error state. True if error occurred
        :rtype: boolean
        """
        res = self._post(
            f"/identity/profiles/{public_profile_id}/profileActions?action=disconnect",
            headers={
                "accept": "application/vnd.linkedin.normalized+json+2.1"},
        )
        # res = self._post(
        #     f"/voyagerRelationshipsDashInvitations/urn%3Ali%3Afsd_invitation%3A{invite_urn_id}?action=withdraw",
        #     headers={
        #         "accept": "application/vnd.linkedin.normalized+json+2.1"},
        # )

        return res.status_code == 200, res.status_code, res.text
    

    def get_invitations(self, start=0, limit=3):
        """Fetch connection invitations for the currently logged in user.

        :param start: How much to offset results by
        :type start: int
        :param limit: Maximum amount of invitations to return
        :type limit: int

        :return: List of invitation objects
        :rtype: list
        """
        params = {
            "start": start,
            "count": limit,
            "includeInsights": True,
            "q": "receivedInvitation",
        }

        res = self._fetch(
            "/relationships/invitationViews",
            params=params,
        )

        if res.status_code != 200:
            return []

        response_payload = res.json()
        return [element["invitation"] for element in response_payload["elements"]]


    def get_urn_id_from_public_id(self, public_id):
        """Get the profile URN ID for a given profile public ID.
        :param public_id: LinkedIn public ID for a profile
        :type public_id: str
        """
        data = self.get_profile(public_id)
        return data["profile_id"]

    def get_user_profile(self, use_cache=True):
        """Get the current user profile. If not cached, a network request will be fired.
        :return: Profile data for currently logged in user
        :rtype: dict
        """
        me_profile = self.client.metadata.get("me")
        if not self.client.metadata.get("me") or not use_cache:
            res = self._fetch(f"/me")
            if res is None or res.status_code == 403 or res.status_code == 401:
                sdr = self.client_sdr
                send_slack_message(
                    message=f"SDR {sdr.name} (#{sdr.id}) returned a {res.status_code} response from LinkedIn. Investigate?",
                    webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
                )
                return None
            if res is None:
                return None
            me_profile = res.json()
            # cache profile
            self.client.metadata["me"] = me_profile

        client_sdr = ClientSDR.query.get(self.client_sdr_id)
        if client_sdr.title == None or len(client_sdr.title) < 2:
            client_sdr.title = me_profile["miniProfile"]["occupation"]
            db.session.add(client_sdr)
            db.session.commit()

        return me_profile

    def send_message(self, message_body, conversation_urn_id=None, recipients=None):
        """Send a message to a given conversation.
        :param message_body: Message text to send
        :type message_body: str
        :param conversation_urn_id: LinkedIn URN ID for a conversation
        :type conversation_urn_id: str, optional
        :param recipients: List of profile urn id's
        :type recipients: list, optional
        :return: Error state. If True, an error occured.
        :rtype: boolean
        """
        params = {"action": "create"}

        if not (conversation_urn_id or recipients):
            self.logger.debug("Must provide [conversation_urn_id] or [recipients].")
            return True

        message_event = {
            "eventCreate": {
                "originToken": str(uuid.uuid4()),
                "value": {
                    "com.linkedin.voyager.messaging.create.MessageCreate": {
                        "attributedBody": {
                            "text": message_body,
                            "attributes": [],
                        },
                        "attachments": [],
                    }
                },
                "trackingId": generate_trackingId_as_charString(),
            },
            "dedupeByClientGeneratedToken": False,
        }

        if conversation_urn_id and not recipients:
            res = self._post(
                f"/messaging/conversations/{conversation_urn_id}/events",
                params=params,
                data=json.dumps(message_event),
            )
            if res is not None:
                response = res.json()
                msg_urn_id = response.get("value", {}).get("backendEventUrn", "")
                msg_urn_id = msg_urn_id.replace("urn:li:messagingMessage:", "")
                if msg_urn_id:
                    return msg_urn_id

        elif recipients and not conversation_urn_id:
            message_event["recipients"] = recipients
            message_event["subtype"] = "MEMBER_TO_MEMBER"
            payload = {
                "keyVersion": "LEGACY_INBOX",
                "conversationCreate": message_event,
            }
            res = self._post(
                f"/messaging/conversations",
                params=params,
                data=json.dumps(payload),
            )
            if res is not None:
                response = res.json()
                msg_urn_id = response.get("value", {}).get("backendEventUrn", "")
                msg_urn_id = msg_urn_id.replace("urn:li:messagingMessage:", "")
                if msg_urn_id:
                    return msg_urn_id

        return False

    def get_conversation_details(self, profile_urn_id):
        """Fetch conversation (message thread) details for a given LinkedIn profile.
        :param profile_urn_id: LinkedIn URN ID for a profile
        :type profile_urn_id: str
        :return: Conversation data
        :rtype: dict
        """
        # passing `params` doesn't work properly, think it's to do with List().
        # Might be a bug in `requests`?
        res = self._fetch(
            f"/messaging/conversations?\
            keyVersion=LEGACY_INBOX&q=participants&recipients=List({profile_urn_id})"
        )
        if res.status_code == 403:
            sdr = self.client_sdr
            send_slack_message(
                message=f"SDR {sdr.name} (#{sdr.id}) returned a 403 response from LinkedIn. Investigate?",
                webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
            )
            return None
        if res is None:
            return None

        try:
            data = res.json()
            data["elements"]
        except:
            print("Failed to get request JSON: ", res)
            return None

        if data["elements"] == []:
            return {}

        item = data["elements"][0]
        item["id"] = get_id_from_urn(item["entityUrn"])

        return item

    def get_conversations(self, limit=20):
        """Fetch list of conversations the user is in.
        :return: List of conversations
        :rtype: list
        """
        params = {"keyVersion": "LEGACY_INBOX", "start": 1}

        if limit == 20:
            res = self._fetch(f"/messaging/conversations", params=params)
            if res.status_code == 403:
                sdr = self.client_sdr
                send_slack_message(
                    message=f"SDR {sdr.name} (#{sdr.id}) returned a 403 response from LinkedIn. Investigate?",
                    webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
                )
                return None
            if res is None:
                return None
            return res.json()
        else:
            conversations = []
            for i in range(math.ceil(limit / 20)):
                q_param = (
                    ""
                    if len(conversations) == 0
                    else f'?createdBefore={conversations[-1].get("events")[0].get("createdAt")}'
                )
                res = self._fetch(f"/messaging/conversations{q_param}", params=params)
                result = (
                    res.json()["elements"] if res and res.status_code != 403 else []
                )
                if isinstance(result, list):
                    conversations += result
            return conversations[:limit]

    def get_conversation(self, conversation_urn_id, limit=20, retries=3):
        try:
            return self.get_conversation_helper(conversation_urn_id, limit)
        except:
            if retries > 0:
                sleep(2)
                return self.get_conversation(conversation_urn_id, limit, retries - 1)
            else:
                return []

    def get_conversation_helper(self, conversation_urn_id, limit=20):
        """Fetch data about a given conversation.
        :param conversation_urn_id: LinkedIn URN ID for a conversation
        :type conversation_urn_id: str
        :return: Conversation data
        :rtype: dict
        """
        if limit == 20:
            res = self._fetch(f"/messaging/conversations/{conversation_urn_id}/events")
            if res.status_code == 403:
                sdr = self.client_sdr
                send_slack_message(
                    message=f"SDR {sdr.name} (#{sdr.id}) returned a 403 response from LinkedIn. Investigate?",
                    webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
                )
                return None
            if res is None:
                return None
            try:
                return res.json()["elements"]
            except:
                print("Failed to get request JSON: ", res)
                return None
        else:
            messages = []
            for i in range(math.ceil(limit / 20)):
                q_param = "" if len(messages) == 0 else f"?start={i*20}"
                res = self._fetch(
                    f"/messaging/conversations/{conversation_urn_id}/events{q_param}"
                )
                try:
                    result = (
                        res.json()["elements"] if res and res.status_code != 403 else []
                    )
                except:
                    result = []
                if isinstance(result, list):
                    messages += result
            return messages[:limit]

    def get_mail_box(self, profile_urn_id):
        # TODO: This is still in progress!
        """Fetch conversation mail box data for a given LinkedIn profile.
        :param profile_urn_id: LinkedIn profile URN ID
        :type profile_urn_id: str
        :return: Mail box data
        :rtype: dict
        """
        encode_str = urllib.parse.quote(f"urn:li:fsd_profile:{profile_urn_id}")
        # TODO: Get queryId
        res = self._fetch(
            f"/voyagerMessagingGraphQL/graphql?queryId=messengerConversations.2782734f1f251808c1959921bd56a2e4&variables=(mailboxUrn:{encode_str})"
        )
        if res.status_code == 403:
            sdr = self.client_sdr
            send_slack_message(
                message=f"SDR {sdr.name} (#{sdr.id}) returned a 403 response from LinkedIn. Investigate?",
                webhook_urls=[URL_MAP["operations-li-invalid-cookie"]],
            )
            return None
        if res is None:
            return None

        return res.json()


    def graphql_search_people(
            self,
            job_title: str,
            regions: list[str],
            limit: Optional[int],
            offset: int
    ) -> list[dict]:
        """Get list of user's urns by job_title and regions."""
        count = self._MAX_SEARCH_COUNT
        if limit is None:
            limit = -1

        results = []
        while True:
            # when we're close to the limit, only fetch what we need to
            if limit > -1 and limit - len(results) < count:
                count = limit - len(results)

            default_params = {
                "origin": "FACETED_SEARCH",
                "start": len(results) + offset,
            }

            res = self._fetch(
                (f"/graphql?variables=(start:{default_params['start']},origin:{default_params['origin']},"
                 f"query:(keywords:{job_title},flagshipSearchIntent:SEARCH_SRP,"
                 f"queryParameters:List((key:geoUrn,value:List({','.join(regions)})),"
                 f"(key:resultType,value:List(PEOPLE))),"
                 f"includeFiltersInResponse:false))&=&queryId=voyagerSearchDashClusters"
                 f".b0928897b71bd00a5a7291755dcd64f0"),
                headers={"accept": "application/vnd.linkedin.normalized+json+2.1"},
            )

            data = json.loads(res.text)

            new_elements = []
            elements = data.get("included", [])

            for element in elements:
                if element.get("template", None) and element.get("template") == "UNIVERSAL":
                    urn_id = element["entityUrn"].split("(")[-1].split(":")[-1].split(",")[0]
                    element_dict = {
                        "entity_urn": urn_id,
                        "full_name": element["title"]["text"],
                        "profile_url": element["navigationContext"]["url"]
                    }
                    new_elements.append(element_dict)

            results.extend(new_elements)

            # break the loop if we're done searching
            # NOTE: we could also check for the `total` returned in the response.
            # This is in data["data"]["paging"]["total"]
            if (
                    (-1 < limit <= len(results))  # if our results exceed set limit
                    or len(results) / count >= self._MAX_REPEATED_REQUESTS
            ) or len(new_elements) == 0:
                break

            self.logger.debug(f"results grew to {len(results)}")

        return results


    def graphql_get_connections(
            self,
            limit: Optional[int],
            offset: int
    ) -> list[dict]:
        """Get list of user's urns by job_title and regions."""
        count = self._MAX_SEARCH_COUNT
        if limit is None:
            limit = -1

        results = []
        while True:
            # when we're close to the limit, only fetch what we need to
            if limit > -1 and limit - len(results) < count:
                count = limit - len(results)

            default_params = {
                "origin": "FACETED_SEARCH",
                "start": len(results) + offset,
            }

            res = self._fetch(
                (f"/graphql?variables=(start:{default_params['start']},origin:MEMBER_PROFILE_CANNED_SEARCH,"
                 f"query:(flagshipSearchIntent:SEARCH_SRP,"
                 f"queryParameters:List((key:network,value:List(F)),"
                 f"(key:resultType,value:List(PEOPLE))),"
                 f"includeFiltersInResponse:false))&=&queryId=voyagerSearchDashClusters"
                 f".b0928897b71bd00a5a7291755dcd64f0"),
                headers={"accept": "application/vnd.linkedin.normalized+json+2.1"},
            )

            data = json.loads(res.text)

            print(data['data'].keys())

            new_elements = []
            elements = data.get("included", [])

            for element in elements:
                if element.get("template", None) and element.get("template") == "UNIVERSAL":
                    urn_id = element["entityUrn"].split("(")[-1].split(":")[-1].split(",")[0]
                    element_dict = {
                        "entity_urn": urn_id,
                        "full_name": element["title"]["text"],
                        "profile_url": element["navigationContext"]["url"]
                    }
                    new_elements.append(element_dict)

            results.extend(new_elements)

            # break the loop if we're done searching
            # NOTE: we could also check for the `total` returned in the response.
            # This is in data["data"]["paging"]["total"]
            if (
                    (-1 < limit <= len(results))  # if our results exceed set limit
                    or len(results) / count >= self._MAX_REPEATED_REQUESTS
            ) or len(new_elements) == 0:
                break

            self.logger.debug(f"results grew to {len(results)}")

        return results


    def graphql_get_sales_nav(
            self,
            keyword,
            years_of_experience,
    ) -> list[dict]:
        """."""

        # res = self._fetch(
        #         (f"/sales-api/salesApiLeadSearch?q=searchQuery&query=(recentSearchParam:(id:3005739300,doLogHistory:true),filters:List((type:COMPANY_TYPE,values:List((id:P,text:Privately%20Held,selectionType:INCLUDED))),(type:FIRST_NAME,values:List((text:John,selectionType:INCLUDED)))))&start=0&count=25&trackingParam=(sessionId:gcExQLjFT7ygsKn5%2Bs6L6A%3D%3D)&decorationId=com.linkedin.sales.deco.desktop.searchv2.LeadSearchResult-13"),
        #         base_request=True,

        # )

        # print(res.text)

        # data = res.json()

        # print(data['data'].keys())

        return make_search(keyword, years_of_experience)


