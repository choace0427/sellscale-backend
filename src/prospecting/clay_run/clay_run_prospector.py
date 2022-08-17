"""
Given
- Location
- Headline
- Industry
- Experience Title

Generate a Clay Table of 230 results
Add the Bio Field
Export Data to a normalized CSV file
Delete All Existing Tables
"""

from dataclasses import dataclass
from threading import Lock
from typing import List

import pandas as pd
from numpy import block

from integrations.clay_run.clay_run_client import ClayRunClient
from src.utils.abstract.attr_utils import deep_get
from src.utils.benders.json_bender import JsonBender
from src.utils.datetime.dateformat_utils import DateFormat, format_datestring
from src.utils.datetime.dateutils import now_in_utc
from src.utils.random_string import generate_random_alphanumeric
from src.utils.sleep import sleep_with_progress
from src.utils.yaml_config import load_yaml_from_file
from src.prospecting.clay_run.configs import ProspectingConfig


@dataclass
class ClayRunScrapeConfig:
    table_name: str
    source_config: ProspectingConfig


class ClayRunProspector:
    _SLEEP_AUGMENTATION_SECONDS = 20

    def __init__(self) -> None:
        self._client = ClayRunClient()
        self._table_lock = Lock()

    def prospect_sync(self, prospecting_config: ProspectingConfig) -> List[dict]:
        self._table_lock.acquire(blocking=True)
        try:
            result = self._prospect_sync(prospecting_config=prospecting_config)
        except Exception:
            self._table_lock.release()
            raise

        self._table_lock.release()
        return result

    def _get_table_name(self) -> str:
        return f'{format_datestring(now_in_utc(), DateFormat.YYYY_MM_DD)}_{generate_random_alphanumeric(10)}'

    def _prospect_sync(self, prospecting_config: ProspectingConfig) -> List[dict]:
        print('Deleting Tables in Workspace')
        self._client.delete_all_tables_in_workspace()

        print('Creating new table...')
        table = self._client.create_table(self._get_table_name())
        print(
            f'Created {deep_get(table, "table.id")} - {deep_get(table, "table.name")}'
        )

        print('Clearing default records')
        table_id = deep_get(table, 'table.id')
        view_id = deep_get(table, 'table.views.0.id')
        self._client.clear_table(table_id=table_id)

        print('Adding LinkedIn Source to Table')
        self._client.add_source_to_table(prospecting_config, table_id)
        bio_field_data = self._client.add_bio_to_table(table_id=table_id)
        bio_field_id = deep_get(bio_field_data, 'id')

        print(f'Added source + bio field ({bio_field_id}). Waiting for Augmentation.')
        print(
            f'You can check it out here: https://app.clay.run/workspaces/{self._client.workspace_id()}/tables/{table_id}/views/{view_id}'
        )

        print(
            f'sleeping for {self._SLEEP_AUGMENTATION_SECONDS}s to allow for augmentation.'
        )
        sleep_with_progress(self._SLEEP_AUGMENTATION_SECONDS)
        records = self._client.get_records_in_view(table_id, view_id)

        bender = JsonBender(
            bender_dict=load_yaml_from_file(
                'src/prospecting/benders/clay_run_format_bender.yml',
                additional_vars={'bio_field_id': bio_field_id},
            )
        )
        results = bender.bend_list(deep_get(records, 'results'))
        df = pd.DataFrame(results)
        results = df.to_dict('records')
        final_results = []
        for i, result in enumerate(results):
            result[''] = f'{i}'
            final_results.append(result)

        return final_results
