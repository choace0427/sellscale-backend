import requests

from integrations.base.auth.cookie_auth_base import CookieValueAuthBase
from src.prospecting.clay_run.configs import ProspectingConfig
from src.utils.abstract.attr_utils import deep_get
from src.utils.crypto_box import CryptoBox


class ClayRunClient:
    _URL_WORKSPACE_INFO = "https://api.clay.run/v3/workspaces/{workspace_id}"
    _URL_CREATE_TABLE = "https://api.clay.run/v3/tables"
    _URL_TABLE_RECORD = "https://api.clay.run/v3/tables/{table_id}"
    _URL_RECORDS_IN_VIEW = (
        "https://api.clay.run/v3/tables/{table_id}/views/{view_id}/records"
    )
    _URL_TABLE_RECORDS = "https://api.clay.run/v3/tables/{table_id}/records"
    _URL_TABLE_FIELDS = "https://api.clay.run/v3/tables/{table_id}/fields"

    _URL_SOURCES = "https://api.clay.run/v3/sources"

    _MAX_RECORDS_TO_PULL = 500
    _MAX_RECORDS_TO_PROCESS = 230

    def __init__(self) -> None:
        self._workspace_id = "6487"

        cookie = CryptoBox().decrypt_from_file("bags/clay_run.cookie.bag")
        self._auth = CookieValueAuthBase("claysession", cookie)

    def workspace_id(self) -> str:
        return self._workspace_id

    def get_tables_in_workspace(self) -> dict:
        response = requests.get(
            self._URL_WORKSPACE_INFO.format(workspace_id=self._workspace_id),
            auth=self._auth,
        )
        response.raise_for_status()
        return response.json()

    def delete_table_in_workspace(self, table_id: str):
        response = requests.delete(
            self._URL_TABLE_RECORD.format(table_id=table_id), auth=self._auth
        )
        response.raise_for_status()

    def delete_all_tables_in_workspace(self):
        tables = self.get_tables_in_workspace()
        for table_id in deep_get(tables, "tables").keys():
            self.delete_table_in_workspace(table_id)

    def create_table(self, title: str):
        response = requests.post(
            self._URL_CREATE_TABLE,
            auth=self._auth,
            json={
                "icon": {"emoji": "🧙🏻‍♂️"},
                "workspaceId": self._workspace_id,
                "type": "people",
                "template": "people_basic",
                "parentFolderId": None,
                "name": title,
            },
        )
        response.raise_for_status()
        return response.json()

    def clear_table(self, table_id: str):
        table_details = self._get_table_details(table_id)
        record_ids = list(
            map(
                lambda x: deep_get(x, "id"),
                deep_get(
                    self.get_records_in_view(
                        table_id=table_id, view_id=deep_get(table_details, "views.0.id")
                    ),
                    "results",
                ),
            )
        )

        response = requests.delete(
            self._URL_TABLE_RECORDS.format(table_id=table_id),
            auth=self._auth,
            json={"recordIds": record_ids},
        )
        response.raise_for_status()

    def _get_table_details(self, table_id: str):
        response = requests.get(
            self._URL_TABLE_RECORD.format(table_id=table_id),
            auth=self._auth,
        )
        response.raise_for_status()
        return response.json()

    def get_records_in_view(self, table_id: str, view_id: str):
        # WARNING: Fails to account for pagination which is fine since free account is limited to 250 results anyway.

        response = requests.get(
            self._URL_RECORDS_IN_VIEW.format(table_id=table_id, view_id=view_id),
            auth=self._auth,
            params={"limit": self._MAX_RECORDS_TO_PULL},
        )
        response.raise_for_status()

        return response.json()

    def add_source_to_table(self, source: ProspectingConfig, table_id: str):
        source_id = self._create_source(source)
        response = requests.patch(
            self._URL_TABLE_RECORD.format(table_id=table_id),
            auth=self._auth,
            json={
                "sourceSettings": {
                    "addSource": {
                        "name": "LinkedIn Profiles",
                        "sourceId": source_id,
                        "isPinned": False,
                    },
                    "newActionFields": [
                        {
                            "type": "action",
                            "name": "Enrich Person",
                            "typeSettings": {
                                "actionKey": "enrich-person-with-coresignal",
                                "actionVersion": 1,
                                "actionPackageId": "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
                                "inputsBinding": [
                                    {
                                        "name": "member_url",
                                        "formulaText": "{{ source }}.id",
                                    }
                                ],
                                "dataTypeSettings": {"type": "json"},
                            },
                            "fieldId": "f_source_enrich_person",
                            "isPinned": True,
                        }
                    ],
                    "formulaOverrides": [
                        {
                            "fieldIdOrEnum": "f_person_linkedin_url",
                            "formulaText": "{{ action0 }}.canonical_url",
                        }
                    ],
                }
            },
        )
        response.raise_for_status()

    def _create_source(self, source: ProspectingConfig) -> str:
        response = requests.post(
            self._URL_SOURCES,
            auth=self._auth,
            json={
                "name": f"{source.location} {source.headline} LinkedIn Profiles",
                "workspaceId": self._workspace_id,
                "type": "v3-action",
                "typeSettings": {
                    "name": "LinkedIn Profiles",
                    "description": "Query LinkedIn data to find people.",
                    "iconType": "LinkedInSource",
                    "actionKey": "find-member-ids-with-coresignal-source",
                    "previewActionKey": "find-member-ids-with-coresignal-source",
                    "actionPackageId": "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
                    "recordsPath": "ids",
                    "defaultPreviewText": "LinkedIn Profile",
                    "idPath": "id",
                    "isAdmin": False,
                    "sourceTableOutputs": {
                        "people": {
                            "addOrUpdateActionFields": [
                                {
                                    "name": "Enrich Person",
                                    "actionVersion": 1,
                                    "actionPackageId": "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
                                    "actionKey": "enrich-person-with-coresignal",
                                    "inputMappings": [
                                        {"name": "member_url", "path": ["id"]}
                                    ],
                                    "actionOutputMappings": [
                                        {
                                            "path": ["canonical_url"],
                                            "mapToFieldId": "f_person_linkedin_url",
                                        }
                                    ],
                                    "fieldId": "f_source_enrich_person",
                                    "isPinned": True,
                                }
                            ]
                        },
                        "peoplev2": {
                            "addOrUpdateActionFields": [
                                {
                                    "name": "Enrich Person",
                                    "actionVersion": 1,
                                    "actionPackageId": "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
                                    "actionKey": "enrich-person-with-coresignal",
                                    "inputMappings": [
                                        {"name": "member_url", "path": ["id"]}
                                    ],
                                    "actionOutputMappings": [
                                        {
                                            "path": ["canonical_url"],
                                            "mapToFieldId": "person/linkedIn/url",
                                        }
                                    ],
                                    "fieldId": "f_source_enrich_person",
                                    "isPinned": True,
                                }
                            ]
                        },
                        "spreadsheet": {
                            "addOrUpdateActionFields": [
                                {
                                    "name": "Enrich Person",
                                    "actionVersion": 1,
                                    "actionPackageId": "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
                                    "actionKey": "enrich-person-with-coresignal",
                                    "inputMappings": [
                                        {"name": "member_url", "path": ["id"]}
                                    ],
                                    "fieldId": "f_source_enrich_person",
                                    "isPinned": True,
                                }
                            ]
                        },
                    },
                    "stages": ["Inputs"],
                    "tableNameInputFields": ["member_location", "title"],
                    "isSourcePinned": False,
                    "inputs": {
                        "member_location": f'"{source.location}"',
                        "limit": f'"{self._MAX_RECORDS_TO_PROCESS}"',
                        "title": f'"{source.headline}"',
                        "member_experience_title": f'"{source.headline}"',
                        "member_industry": f'"{source.industry}"',
                    },
                },
            },
        )
        response.raise_for_status()
        return deep_get(response.json(), "id")

    def add_bio_to_table(self, table_id: str):
        response = requests.post(
            self._URL_TABLE_FIELDS.format(table_id=table_id),
            auth=self._auth,
            json={
                "type": "people",
                "name": "Bio",
                "typeSettings": {
                    "dataTypeSettings": {"type": "text"},
                    "peopleAttribute": "PERSON_BIO",
                },
            },
        )
        response.raise_for_status()
        return response.json()
