import requests
from requests.exceptions import ConnectionError, Timeout
from src.voyager.test_exceptions import raise_for_error, LinkedInError, ReadTimeoutError, Server5xxError, LinkedInTooManyRequestsError

import backoff

REQUEST_TIMEOUT = 3000
BACKOFF_MAX_TRIES_REQUEST = 5

class LinkedInClient():

    BASE_URL = "https://www.linkedin.com"
    PEOPLE_URL_PREFIX = "sales-api/salesApiLeadSearch?q=searchQuery&query=(spellCorrectionEnabled:true"
    PEOPLE_URL_SUFFIX = "decorationId=com.linkedin.sales.deco.desktop.searchv2.LeadSearchResult-7"
    
    COMPANY_URL_PREFIX = "sales-api/salesApiCompanies"
    COMPANY_URL_SUFFIX = f"""decoration=%28entityUrn%2Cname%2Cdescription%2Cindustry%2CemployeeCount%2CemployeeDisplayCount%2CemployeeCountRange%2Clocation%2Cheadquarters%2Cwebsite%2Crevenue%2CformattedRevenue%2CemployeesSearchPageUrl%2CflagshipCompanyUrl%29"""

    def __init__(self):
        self.keyword = "Amazon"
        self.__cookie = 'bcookie="v=2&4df6479c-c7f5-432e-868c-7a2876a6f4db"; bscookie="v=1&20230724232332222cb3c8-c87e-41b1-83f0-88e569d328e1AQFqS0D8HHzPDJ50XDD8GYUDrf-xDCT1"; li_gp=MTsxNjkwMjQxMDEyOzA=; li_sugr=4046dce3-1bb1-45f2-8af6-9e67a8ae3d48; _guid=01cd4609-3859-4760-9f0d-be2928497e39; li_theme=light; li_theme_set=app; timezone=America/Denver; AnalyticsSyncHistory=AQKLC07p95TSAgAAAYn3RYWTMu7ZLhvkGkYgaCUZAO2BLFK4hoOJJFX-4HJPi5w3pYpvcJodIgbaNszWaW0xMQ; lms_ads=AQEQvhvyQOHwSQAAAYn3RYXl8nwptBFFGCwmM3JRvHZvPOYBnra2-bHtVwUvv4RiSrAEFrdv94B-aamykh2OjlZYVTWsz-nh; lms_analytics=AQEQvhvyQOHwSQAAAYn3RYXl8nwptBFFGCwmM3JRvHZvPOYBnra2-bHtVwUvv4RiSrAEFrdv94B-aamykh2OjlZYVTWsz-nh; li_rm=AQEXT_u77ytG6QAAAYn3RZSL1mzYLy9hlpN4R1AW8Qa3P8d3CwdHfPMCdUl5BHHJ7VMAHleKniXfZPllU5gP3yrTjhNwG8Q8y2Di23TdNAM6AJB38CAqZAMM; visit=v=1&M; PLAY_LANG=en; liveagent_oref=https://www.linkedin.com/sales/home; liveagent_ptid=e4b061cb-4151-407c-b3dc-79a59cdd2977; fcookie=AQGEbGncx5HFdQAAAYn7mx9F2Lil2jDis87KjNYoh1xpy1O1VhcP3x0Au2zOaQ0N5iu15lP_UZ3a_RvT0eBPI4vaUHBR82DYzu0SM4SJ3OTrTducF4Pcd8fhzqT0pPRh5GHKmhi8_UD7zN3wciQsWfL4xjQI5dCOTY-NoGf3s854rdDyoQJVz7nuWADBW6RcxACkhv09RENjG4E6wblBpn83t-SXyM9h84oeOGZbt6r6QjHzpMk-JTHZkgRZZTHEcY4pp8T7eFCLo7Xx48/8JyKgsC/AIBIG5P8tz2lWU8fo5rTxRsqRY2oUdUVNmhtyd2wxiniHL6WPJfHA==; fid=AQHgBsBudkC2PgAAAYn7m_anolBeBkIilw_heqWipx0uFUrJmVkJg1XwlI9is-hyttT_TpIEqZb4KQ; li_g_recent_logout=v=1&true; liap=true; li_at=AQEDARUeh_0CIquuAAABigGhPnUAAAGKJa3CdVYAS-MT7luAT1nlrVcm64S2tqEoYqw4zDp-OyZAdDPUQGvk01214wBLBAYXpa2Z3ilmrIjmOjMbIoz1Tmd5l_2Zf5hzf-FC5fBU4uSoee-ExzFfRNnv; JSESSIONID="ajax:5187171584544380618"; li_gpc=1; UserMatchHistory=AQL0gzwtRkmpmAAAAYoBoUX1Z3-L1rofyhd1Cc-xNf8P6H4R0aoHUobnbFppEWNkxBgLIjjZzzqvwLXTFT58yGL_aKX83A76vXhJEciK1ctQBrOWgr7jAGBpFZfZoxovfJG1JtL1RcH5esSw64ANKLsxRGUKMDfJENL7uaoeSIwL6Hb-pgt4oFguHPENtzBxRaTsdXABArcoL-RW-tFG4hPp63gHFj7S7aZwbGf2YEVZ2b71mlYyMxs5Zh5yRZdljKu1hy3CrAQikpR_c6rxzhigocA_BRxPMB0K6V5YqIVA6pBmOWVeb0pWInbqhjdYqXYkIaNS1UFJQRMSeAo9Xcf4EoPo33k; lidc="b=OB29:s=O:r=O:a=O:p=O:g=6351:u=1014:x=1:i=1692244461:t=1692289645:v=2:sig=AQFtjnONdtDWCUegiikV68A4w8T2oyp0"; li_a=AQJ2PTEmc2FsZXNfY2lkPTExMTkxOTk0MDIlM0ElM0E0OTA0MDAwMDKdlCgkVuuq29wliKmkym153no6dw; lang=v=2&lang=en-US; liveagent_sid=9f67bde8-19bf-4e39-aa6b-1a53dd9632ba; liveagent_vc=5'
        self.__csrf_token = "ajax:5187171584544380618"
        self.__li_identity = "dXJuOmxpOm1lbWJlcjozNTQzMjI0Mjk"
        self.__verified = False
        self.__session = requests.Session()

    def __enter__(self):
        self.__verified = self.check_access()
        
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.__session.close()
    
    def __headers(self):
        headers = {}
        headers["accept"] = "*/*"
        headers["accept-language"] = "en-US,en;q=0.9"
        headers["cache-control"] = "no-cache"
        headers["csrf-token"] = self.__csrf_token
        headers["pragma"] = "no-cache"
        headers["x-li-identity"] = self.__li_identity
        headers["cookie"] = self.__cookie
        headers["x-li-lang"] = "en_US"
        headers["x-restli-protocol-version"] = "2.0.0"
        headers["sec-ch-ua"] = "\"Google Chrome\";v=\"93\", \" Not;A Brand\";v=\"99\", \"Chromium\";v=\"93\""
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = "\"macOS\""
        headers["sec-fetch-dest"] = "empty"
        headers["sec-fetch-mode"] = "cors"
        headers["sec-fetch-site"] = "same-origin"
        headers["x-li-page-instance"] = "urn:li:page:d_sales2_search_people;h3m149w6RCqmiOtycNuBkA=="

        return headers
    
    def get_company_url(self, linkedin_id):
        url = f"{self.BASE_URL}/{self.COMPANY_URL_PREFIX}/{linkedin_id}?{self.COMPANY_URL_SUFFIX}"
        
        return url

    def get_people_search_url(self, keyword, company_size, region, years_of_experience, tenure):

        filters = f"filters:List((type:YEARS_OF_EXPERIENCE,values:List((id:{years_of_experience})))),keywords:{keyword})"
        url = f"{self.BASE_URL}/{self.PEOPLE_URL_PREFIX},{filters}&{self.PEOPLE_URL_SUFFIX}"

        print("URL", url)
        
        return url
    
    @backoff.on_exception(
        backoff.expo,
        (Server5xxError, ReadTimeoutError, ConnectionError, Timeout),
        max_tries=3,
        factor=2)
    def check_access(self):

        if self.__cookie is None:
            raise Exception('Error: Missing cookie in tap config.json.')
        
        url = f"{self.BASE_URL}/sales"

        try:
            response = self.__session.get(url=url, timeout=REQUEST_TIMEOUT, headers=self.__headers())
        except requests.exceptions.Timeout as err:
            print(f'TIMEOUT ERROR: {err}')
            raise ReadTimeoutError

        if response.status_code != 200:
            print(f'Error status_code = {response.status_code}')
            raise_for_error(response)
        else:
            return True

    @backoff.on_exception(
        backoff.expo,
        (Server5xxError, ReadTimeoutError, ConnectionError, Timeout, LinkedInTooManyRequestsError),
        max_tries=BACKOFF_MAX_TRIES_REQUEST,
        factor=10)
    def perform_request(self,
                        method,
                        url=None,
                        params=None,
                        json=None,
                        stream=False,
                        **kwargs):
        
        try:
            response = self.__session.request(method=method,
                                              url=url,
                                              params=params,
                                              json=json,
                                              stream=stream,
                                              timeout=REQUEST_TIMEOUT,
                                              **kwargs)

            if response.status_code >= 500:
                print(f'Error status_code = {response.status_code}')
                raise Server5xxError()

            if response.status_code != 200:
                print(f'Error status_code = {response.status_code}')
                raise_for_error(response)
            
            return response

        except requests.exceptions.Timeout as err:
            print(f'TIMEOUT ERROR: {err}')
            raise ReadTimeoutError(err)

    def get_request(self, url, params=None, json=None, **kwargs):
        
        if not self.__verified:
            self.__verified = self.check_access()

        response = self.perform_request(method="get",
                                            url=url,
                                            params=params,
                                            json=json,
                                            headers=self.__headers(),
                                            **kwargs)

        response_json = response.json()

        return response_json
