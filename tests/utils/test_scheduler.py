from test_utils import test_app
import mock
from src.utils.scheduler import *


@mock.patch("src.automation.inbox_scraper.scrape_all_inboxes.delay")
def test_scrape_all_inboxes_job(patch):
    scrape_all_inboxes_job()
    assert patch.call_count == 1


@mock.patch("src.ml.services.check_statuses_of_fine_tune_jobs.delay")
def test_refresh_fine_tune_statuses_job(patch):
    refresh_fine_tune_statuses_job()
    assert patch.call_count == 1
