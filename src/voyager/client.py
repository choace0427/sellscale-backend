import requests
import logging

from model_import import ClientSDR
from bs4 import BeautifulSoup
import json
from app import db
from requests.cookies import cookiejar_from_dict

logger = logging.getLogger(__name__)


class ChallengeException(Exception):
    pass


class UnauthorizedException(Exception):
    pass


class Client(object):
    """
    Class to act as a client for the Linkedin API.
    """

    # Settings for general Linkedin API calls
    LINKEDIN_BASE_URL = "https://www.linkedin.com"
    API_BASE_URL = f"{LINKEDIN_BASE_URL}/voyager/api"
    REQUEST_HEADERS = {
        # "user-agent": " ".join(
        #     [
        #         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5)",
        #         "AppleWebKit/537.36 (KHTML, like Gecko)",
        #         "Chrome/83.0.4103.116 Safari/537.36",
        #     ]
        # ),
        # "accept": "application/vnd.linkedin.normalized+json+2.1",
        "accept-language": "en-AU,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "x-li-lang": "en_US",
        "x-restli-protocol-version": "2.0.0",
        # "x-li-track": '{"clientVersion":"1.2.6216","osName":"web","timezoneOffset":10,"deviceFormFactor":"DESKTOP","mpName":"voyager-web"}',
    }

    # Settings for authenticating with Linkedin
    AUTH_REQUEST_HEADERS = {
        "X-Li-User-Agent": "LIAuthLibrary:3.2.4 \
                            com.linkedin.LinkedIn:8.8.1 \
                            iPhone:8.3",
        "User-Agent": "LinkedIn/8.8.1 CFNetwork/711.3.18 Darwin/14.0.0",
        "X-User-Language": "en",
        "X-User-Locale": "en_US",
        "Accept-Language": "en-us",
    }

    def __init__(self, *, debug=False, refresh_cookies=False, proxies={}):
        self.session = requests.session()
        self.session.proxies.update(proxies)
        self.session.headers.update(Client.REQUEST_HEADERS)
        self.proxies = proxies
        self.logger = logger
        self.metadata = {}
        self._use_cookie_cache = not refresh_cookies

        logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    def _request_session_cookies(self):
        """
        Return a new set of session cookies as given by Linkedin.
        """
        self.logger.debug("Requesting new cookies.")

        res = requests.get(
            f"{Client.LINKEDIN_BASE_URL}/uas/authenticate",
            headers=Client.AUTH_REQUEST_HEADERS,
            proxies=self.proxies,
        )
        return res.cookies

    def _get_cookies_for_sdr_store(self, li_at: str):
        cookies_jar = self._request_session_cookies()
        if not cookies_jar:
            return None

        cookies_jar.set("li_at", li_at)

        return cookies_jar

    def _set_session_cookies(self, cookies, user_agent: str = None):
        """
        Set cookies and user-agent of the current session
        """
        self.session.cookies = cookies
        self.session.headers["csrf-token"] = self.session.cookies["JSESSIONID"].strip(
            '"'
        )

        if not user_agent:
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"

        self.session.headers["user-agent"] = user_agent

    @property
    def cookies(self):
        return self.session.cookies

    def authenticate(self, client_sdr: ClientSDR):
        if self._use_cookie_cache:
            self.logger.debug("Attempting to use cached cookies")
            user_agent = client_sdr.user_agent
            if client_sdr.li_at_token and client_sdr.li_at_token != "INVALID":
                cookies = self._get_cookies_for_sdr_store(client_sdr.li_at_token)
            else:
                try:
                    cookie_jar = cookiejar_from_dict(json.loads(client_sdr.li_cookies))
                    if cookie_jar and cookie_jar.get("li_at"):
                        client_sdr.li_at_token = cookie_jar.get("li_at")
                        client_sdr.last_li_at_token = cookie_jar.get("li_at")
                        db.session.commit()
                        cookies = self._get_cookies_for_sdr_store(
                            cookie_jar.get("li_at")
                        )
                except:
                    cookies = None

            if cookies:
                self.logger.debug("Using cached cookies")
                self._set_session_cookies(cookies, user_agent)
                self._fetch_metadata()
                return

        # self._do_authentication_request(client_sdr)
        self._fetch_metadata()

    def _fetch_metadata(self):
        """
        Get metadata about the "instance" of the LinkedIn application for the signed in user.
        Store this data in self.metadata
        """
        try:
            res = requests.get(
                f"{Client.LINKEDIN_BASE_URL}",
                cookies=self.session.cookies,
                headers=Client.AUTH_REQUEST_HEADERS,
                proxies=self.proxies,
            )
        except Exception as e:
            return

        soup = BeautifulSoup(res.text, "lxml")

        clientApplicationInstanceRaw = soup.find(
            "meta", attrs={"name": "applicationInstance"}
        )
        if clientApplicationInstanceRaw:
            clientApplicationInstanceRaw = (
                clientApplicationInstanceRaw.attrs.get("content") or {}  # type: ignore
            )
            clientApplicationInstance = json.loads(
                clientApplicationInstanceRaw
            )  # type: ignore
            self.metadata["clientApplicationInstance"] = clientApplicationInstance

        clientPageInstanceIdRaw = soup.find(
            "meta", attrs={"name": "clientPageInstanceId"}
        )
        if clientPageInstanceIdRaw:
            clientPageInstanceId = (
                clientPageInstanceIdRaw.attrs.get("content") or {}  # type: ignore
            )
            self.metadata["clientPageInstanceId"] = clientPageInstanceId

    def _do_authentication_request(self, client_sdr: ClientSDR):
        """
        Authenticate with Linkedin.
        Return a session object that is authenticated.
        """
        self._set_session_cookies(self._request_session_cookies(), user_agent=None)

        payload = {  # TODO: get username and password from client_sdr?
            "session_key": "aaronncassar@gmail.com",
            "session_password": "MY-AWESOME-PASSWORD",
            "JSESSIONID": self.session.cookies["JSESSIONID"],
        }

        res = requests.post(
            f"{Client.LINKEDIN_BASE_URL}/uas/authenticate",
            data=payload,
            cookies=self.session.cookies,
            headers=Client.AUTH_REQUEST_HEADERS,
            proxies=self.proxies,
        )

        data = res.json()

        if data and data["login_result"] != "PASS":
            raise ChallengeException(data["login_result"])

        if res.status_code == 401:
            raise UnauthorizedException()

        if res.status_code != 200:
            raise Exception()

        self._set_session_cookies(res.cookies, user_agent=None)
        ClientSDR.query.filter(ClientSDR.id == client_sdr.id).update(
            {"li_cookies": json.dumps(res.cookies.get_dict())}
        )
        db.session.commit()
