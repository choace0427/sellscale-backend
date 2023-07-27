from app import db, app
import pytest
from decorators import use_app_context
import json
from src.automation.models import PhantomBusterSalesNavigatorConfig, PhantomBusterSalesNavigatorLaunch, SalesNavigatorLaunchStatus
from src.automation.phantom_buster.services import collect_and_load_sales_navigator_results, collect_and_trigger_phantom_buster_sales_navigator_launches, get_sales_navigator_launch_result, get_sales_navigator_launches, register_phantom_buster_sales_navigator_url, run_phantom_buster_sales_navigator
from test_utils import test_app, basic_client, basic_client_sdr, basic_pb_sn_config, basic_pb_sn_launch
import mock


@use_app_context
def test_get_sales_navigator_launches():
    client = basic_client()
    sdr = basic_client_sdr(client)
    agent = basic_pb_sn_config(client_sdr=sdr)
    launch = basic_pb_sn_launch(agent, sdr)
    launch_2 = basic_pb_sn_launch(agent, sdr)

    launches = get_sales_navigator_launches(sdr.id)
    assert len(launches) == 2
    assert launches[1]["id"] == launch.id
    assert launches[0]["id"] == launch_2.id


@use_app_context
def test_get_sales_navigator_launch_result():
    client = basic_client()
    sdr = basic_client_sdr(client)
    agent = basic_pb_sn_config(client_sdr=sdr)
    launch = basic_pb_sn_launch(agent, sdr, result_raw=[{"profileUrl": "https://www.linkedin.com/sales/lead/THISISATEST,NAME_SEARCH,Yqtx"}])

    launch_raw, launch_processed = get_sales_navigator_launch_result(sdr.id, launch.id)
    assert launch_raw[0]["profileUrl"] == "https://www.linkedin.com/sales/lead/THISISATEST,NAME_SEARCH,Yqtx"


@use_app_context
def test_register_phantom_buster_sales_navigator_url():
    client = basic_client()
    sdr = basic_client_sdr(client)

    # Using a common pool agent
    common_pool_phantom = basic_pb_sn_config()
    assert len(PhantomBusterSalesNavigatorLaunch.query.all()) == 0
    assert common_pool_phantom.daily_trigger_count == 0
    success, _ = register_phantom_buster_sales_navigator_url(
        sales_navigator_url="sales_navigator_url",
        scrape_count=150,
        client_sdr_id=sdr.id,
        scrape_name='test_name'
    )
    assert success
    assert common_pool_phantom.daily_trigger_count == 1
    assert common_pool_phantom.daily_prospect_count == 150
    launch = PhantomBusterSalesNavigatorLaunch.query.all()
    assert len(launch) == 1
    assert launch[0].client_sdr_id == sdr.id
    assert launch[0].sales_navigator_url == "sales_navigator_url"
    assert launch[0].scrape_count == 150
    assert launch[0].status == SalesNavigatorLaunchStatus.QUEUED
    assert launch[0].name == 'test_name'

    # Now using the client-specific agent (should take priority)
    client_specific_phantom = basic_pb_sn_config(client_sdr=sdr)
    assert len(PhantomBusterSalesNavigatorLaunch.query.all()) == 1
    assert client_specific_phantom.daily_trigger_count == 0
    success, _ = register_phantom_buster_sales_navigator_url(
        sales_navigator_url="sales_navigator_url",
        scrape_count=150,
        client_sdr_id=sdr.id,
        scrape_name='test_name'
    )
    assert success
    assert client_specific_phantom.daily_trigger_count == 1
    assert client_specific_phantom.daily_prospect_count == 150
    launch = PhantomBusterSalesNavigatorLaunch.query.all()
    assert len(launch) == 2


@use_app_context
@mock.patch("src.automation.models.PhantomBusterAgent.get_output_by_container_id", return_value=[{"profileUrl": "https://www.linkedin.com/sales/lead/THISISATEST,NAME_SEARCH,Yqtx"}])
def test_collect_and_load_sales_navigator_results(get_output_by_container_id_mock):
    client = basic_client()
    sdr = basic_client_sdr(client)
    agent = basic_pb_sn_config(client_sdr=sdr, in_use=True)
    agent_id = agent.id
    launch = basic_pb_sn_launch(agent, sdr, pb_container_id="pb_container_id", status=SalesNavigatorLaunchStatus.RUNNING)
    launch_id = launch.id

    assert launch.result_raw is None
    collect_and_load_sales_navigator_results()
    get_output_by_container_id_mock.assert_called_once_with("pb_container_id")
    launch: PhantomBusterSalesNavigatorLaunch = PhantomBusterSalesNavigatorLaunch.query.get(launch_id)
    assert launch.result_raw == [{"profileUrl": "https://www.linkedin.com/sales/lead/THISISATEST,NAME_SEARCH,Yqtx"}]
    assert launch.result_processed == [{"profileUrl": "https://www.linkedin.com/in/THISISATEST"}]
    assert launch.status == SalesNavigatorLaunchStatus.SUCCESS
    agent: PhantomBusterSalesNavigatorConfig = PhantomBusterSalesNavigatorConfig.query.get(agent_id)
    assert agent.in_use is False


@use_app_context
@mock.patch("src.automation.phantom_buster.services.run_phantom_buster_sales_navigator.delay")
def test_collect_and_trigger_phantom_buster_sales_navigator_launches(mock_run_phantom_buster_sales_navigator):
    client = basic_client()
    sdr = basic_client_sdr(client)
    agent = basic_pb_sn_config(client_sdr=sdr)
    agent_id = agent.id
    launch = basic_pb_sn_launch(agent, sdr)

    collect_and_trigger_phantom_buster_sales_navigator_launches()
    mock_run_phantom_buster_sales_navigator.assert_called_once_with(launch.id)
    agent: PhantomBusterSalesNavigatorConfig = PhantomBusterSalesNavigatorConfig.query.get(agent_id)
    assert agent.in_use is True


class MOCK_RUN_PHANTOM_RESPONSE:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self.data = data

    def json(self):
        return {"data": self.data}

@use_app_context
@mock.patch("src.automation.models.PhantomBusterAgent.get_agent_data", return_value={"id": "test_id"})
@mock.patch("src.automation.models.PhantomBusterAgent.update_argument")
@mock.patch("src.automation.models.PhantomBusterAgent.run_phantom", return_value=MOCK_RUN_PHANTOM_RESPONSE(200, {"containerId": "test_container_id"}))
def test_run_phantom_buster_sales_navigator(mock_run_phantom, mock_update_argument, mock_get_agent_data):
    client = basic_client()
    sdr = basic_client_sdr(client)
    agent = basic_pb_sn_config(client_sdr=sdr, in_use=True)
    launch = basic_pb_sn_launch(agent, sdr)
    launch_id = launch.id

    success, _ = run_phantom_buster_sales_navigator(launch.id)
    assert success
    launch: PhantomBusterSalesNavigatorLaunch = PhantomBusterSalesNavigatorLaunch.query.get(launch_id)
    mock_run_phantom.assert_called_once()
    mock_update_argument_calls = mock_update_argument.call_args_list
    assert len(mock_update_argument_calls) == 2
    mock_update_argument.assert_any_call("searches", launch.sales_navigator_url)
    mock_update_argument.assert_any_call("numberOfProfiles", launch.scrape_count)
    mock_get_agent_data.assert_called_once()
    assert launch.pb_container_id == "test_container_id"
    assert launch.status == SalesNavigatorLaunchStatus.RUNNING
