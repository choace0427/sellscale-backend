from app import db, celery

import requests
import os
import json
from datetime import datetime, timedelta
from typing import Optional
from src.automation.models import PhantomBusterAgent, PhantomBusterSalesNavigatorConfig, PhantomBusterSalesNavigatorLaunch, SalesNavigatorLaunchStatus

from src.client.models import Client, ClientSDR


PHANTOMBUSTER_API_KEY = os.environ.get("PHANTOMBUSTER_API_KEY")
DAILY_AGENT_TRIGGER_LIMIT = 4
DAILY_PROSPECT_SCRAPE_LIMIT = 600
MAXIMUM_SCRAPE_PER_LAUNCH = 400


def reset_sales_navigator_config_counts() -> None:
    """Resets the daily counts for the Sales Navigator config

    Returns:
        None
    """
    configs: list[PhantomBusterSalesNavigatorConfig] = PhantomBusterSalesNavigatorConfig.query.all()
    for config in configs:
        config.daily_trigger_count = 0
        config.daily_prospect_count = 0
        db.session.commit()


def get_sales_navigator_launches(client_sdr_id: int) -> list[dict]:
    """Returns all Sales Navigator launches belonging to this SDR

    Args:
        client_sdr_id (int): The ID of the SDR

    Returns:
        list[dict]: List of dictionaries corresponding to the launches
    """
    launches: list[PhantomBusterSalesNavigatorLaunch] = PhantomBusterSalesNavigatorLaunch.query.filter(
        PhantomBusterSalesNavigatorLaunch.client_sdr_id == client_sdr_id,
    ).order_by(
        PhantomBusterSalesNavigatorLaunch.created_at.desc(),
    ).all()

    return [launch.to_dict() for launch in launches]


def get_sales_navigator_launch_result(client_sdr_id: int, launch_id: int) -> tuple[list, list]:
    """Returns the JSON result (to be returned as CSV) corresponding to the launch

    Args:
        client_sdr_id (int): ID of the Client SDR
        launch_id (int): ID of the Sales Navigator Launch

    Returns:
        tuple[list, list]: Tuple of the raw and processed results
    """
    launch: PhantomBusterSalesNavigatorLaunch = PhantomBusterSalesNavigatorLaunch.query.get(launch_id)
    if launch.client_sdr_id != client_sdr_id:
        return None

    return launch.result_raw, launch.result_processed


def create_phantom_buster_sales_navigator_config(linkedin_session_cookie: str, client_sdr_id: Optional[int]) -> int:
    """Creates a PhantomBusterSalesNavigatorConfig entry

    Args:
        linkedin_session_cookie (str): Session cookie used by this agent
        client_sdr_id (Optional[int]): Client SDR ID

    Returns:
        int: PhantomBusterSalesNavigatorConfig ID
    """
    url = "https://api.phantombuster.com/api/v2/agents/save"

    # Construct the name of the PhantomBuster agent
    if client_sdr_id:
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client: Client = Client.query.get(sdr.client_id)
        phantom_name = "LinkedIn Sales Navigator - {company} ({sdr_name})".format(
            company=client.company, sdr_name=sdr.name
        )
    else:
        common_pool_count = ClientSDR.query.filter_by(
            common_pool=True,
            client_sdr_id=None,
            client_id=None,
        ).count()
        phantom_name = "LinkedIn Sales Navigator - Common Pool #{count}".format(count=common_pool_count)

    # Create the PhantomBuster agent
    payload = json.dumps(
        {}
    )
    headers = {
        "X-Phantombuster-Key": PHANTOMBUSTER_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    phantom_uuid = response.json()["id"]

    # Create the PhantomBusterSalesNavigatorConfig entry
    client_id = None
    if client_sdr_id:
        sdr: ClientSDR = ClientSDR.query.get(client_sdr_id)
        client_id = sdr.client_id

    config: PhantomBusterSalesNavigatorConfig = PhantomBusterSalesNavigatorConfig(
        client_id=client_id,
        client_sdr_id=client_sdr_id,
        common_pool=client_sdr_id is None,
        phantom_name=phantom_name,
        phantom_uuid=phantom_uuid,
        linkedin_session_cookie=linkedin_session_cookie,
    )
    db.session.add(config)
    db.session.commit()

    return config.id


def register_phantom_buster_sales_navigator_url(sales_navigator_url: str, scrape_count: int, client_sdr_id: int, scrape_name: str) -> tuple[bool, str]:
    """Registers a Sales Navigator URL to a PhantomBusterSalesNavigatorConfig entry

    Args:
        sales_navigator_url (str): Sales Navigator URL
        scrape_count (int): Number of times to scrape this URL
        client_sdr_id (int): The ID of the Client SDR who is running a Sales Navigator job
        scrape_name (str): Name of the scrape

    Returns:
        tuple[bool, str]: Success and message
    """
    # IMPROVEMENT: IF THERE IS HIGH CUSTOMER DEMAND
    # We can, instead of forcing a job to have an agent tied to it, register a job without an agent
    # then have cron logic which will try to assign an agent to it.

    # Set the scrape_count to a maximum
    scrape_count = min(scrape_count, MAXIMUM_SCRAPE_PER_LAUNCH)

    # Grab the PhantomBusterSalesNavigatorConfig that may belong to this sdr
    config: PhantomBusterSalesNavigatorConfig = PhantomBusterSalesNavigatorConfig.query.filter(
        PhantomBusterSalesNavigatorConfig.client_sdr_id == client_sdr_id,
        PhantomBusterSalesNavigatorConfig.daily_trigger_count < DAILY_AGENT_TRIGGER_LIMIT,
        PhantomBusterSalesNavigatorConfig.daily_prospect_count < DAILY_PROSPECT_SCRAPE_LIMIT,
    ).first()

    # If there is no Agent dedicated to this SDR, grab a random Common Pool agent
    if not config:
        config: PhantomBusterSalesNavigatorConfig = PhantomBusterSalesNavigatorConfig.query.filter(
            PhantomBusterSalesNavigatorConfig.common_pool == True,
            PhantomBusterSalesNavigatorConfig.client_id == None,
            PhantomBusterSalesNavigatorConfig.client_sdr_id == None,
            PhantomBusterSalesNavigatorConfig.linkedin_session_cookie != None,
            PhantomBusterSalesNavigatorConfig.phantom_uuid != None,
            PhantomBusterSalesNavigatorConfig.daily_trigger_count < DAILY_AGENT_TRIGGER_LIMIT,
            PhantomBusterSalesNavigatorConfig.daily_prospect_count < DAILY_PROSPECT_SCRAPE_LIMIT,
        ).order_by(PhantomBusterSalesNavigatorConfig.daily_trigger_count.asc()
        ).order_by(PhantomBusterSalesNavigatorConfig.daily_prospect_count.asc()
        ).first()

    # If there is no Agent available, return
    if not config:
        return False, "No Agents available."

    # Update the PhantomBusterSalesNavigatorConfig entry (increment daily_trigger_count and daily_prospect_count)
    config.daily_trigger_count += 1
    config.daily_prospect_count += min(scrape_count, MAXIMUM_SCRAPE_PER_LAUNCH)
    db.session.commit()

    # Create a PhantomBusterSalesNavigatorLaunch entry
    launch = PhantomBusterSalesNavigatorLaunch(
        sales_navigator_config_id=config.id,
        client_sdr_id=client_sdr_id,
        sales_navigator_url=sales_navigator_url,
        status=SalesNavigatorLaunchStatus.QUEUED,
        scrape_count=scrape_count,
        name=scrape_name,
    )
    db.session.add(launch)
    db.session.commit()

    return True, "Success"


@celery.task(bind=True)
def collect_and_load_sales_navigator_results(self) -> None:
    """Collects and loads Sales Navigator results. Looks for SalesNavigatorLaunch entries with status=RUNNING and pb_container_id set.

    Will query the PhantomBuster API for the results of each pb_container_id, and load the results into the database.

    This function is triggered by a webhook from PhantomBuster.
    """
    def process_phantom_result_raw(result_raw: list[dict]) -> list[dict]:
        if type(result_raw) != list:
            # Most likely the PB Payload is different than expected.
            jsonUrl = result_raw.get('jsonUrl')
            result_raw = requests.get(jsonUrl).json()
        result_processed = []
        for raw_dict in result_raw:
            processed_dict: dict = dict(raw_dict)
            url = processed_dict.get("profileUrl")
            if url:
                processed_url = url.replace('/sales/lead/', '/in/').split(',')[0]
                processed_dict["profileUrl"] = processed_url
            result_processed.append(processed_dict)

        return result_processed

    # Find all SalesNavigatorLaunch entries with status=RUNNING and pb_container_id set
    launches: list[PhantomBusterSalesNavigatorLaunch] = PhantomBusterSalesNavigatorLaunch.query.filter(
        PhantomBusterSalesNavigatorLaunch.status == SalesNavigatorLaunchStatus.RUNNING,
        PhantomBusterSalesNavigatorLaunch.pb_container_id != None,
    ).all()

    for launch in launches:
        # Query the PhantomBuster API for the results of each pb_container_id
        agent: PhantomBusterSalesNavigatorConfig = PhantomBusterSalesNavigatorConfig.query.get(launch.sales_navigator_config_id)
        phantom: PhantomBusterAgent = PhantomBusterAgent(agent.phantom_uuid)
        result_raw = phantom.get_output_by_container_id(launch.pb_container_id)
        result_processed = process_phantom_result_raw(result_raw)

        # If the result exists, then load the result into the database, and mark the launch as complete
        if result_raw:
            # Load the result into the database
            launch.result_raw = result_raw
            launch.result_processed = result_processed

            # Mark the launch as complete
            launch.status = SalesNavigatorLaunchStatus.SUCCESS

            # Clear the error message
            launch.error_message = None

            # Mark the agent as in_use=False
            agent.in_use = False
            db.session.commit()

    return


@celery.task()
def collect_and_trigger_phantom_buster_sales_navigator_launches() -> None:
    """Collects and triggers PhantomBusterSalesNavigatorLaunch entries
    """
    # Find all available SalesNavigator Agents
    agents: list[PhantomBusterSalesNavigatorConfig] = PhantomBusterSalesNavigatorConfig.query.filter(
        PhantomBusterSalesNavigatorConfig.in_use == False,
    ).all()
    agent_ids = [agent.id for agent in agents]

    # Collect all queued PhantomBusterSalesNavigatorLaunch on available agents
    launches: list[PhantomBusterSalesNavigatorLaunch] = PhantomBusterSalesNavigatorLaunch.query.filter(
        PhantomBusterSalesNavigatorLaunch.sales_navigator_config_id.in_(agent_ids),
        PhantomBusterSalesNavigatorLaunch.status == SalesNavigatorLaunchStatus.QUEUED,
    ).all()
    for launch in launches:
        # Mark agents as in use
        agent: PhantomBusterSalesNavigatorConfig = PhantomBusterSalesNavigatorConfig.query.get(launch.sales_navigator_config_id)
        agent.in_use = True
        db.session.commit()

        # Trigger PhantomBusterSalesNavigatorLaunch entry
        run_phantom_buster_sales_navigator.delay(launch.id)

    return


@celery.task(bind=True, max_retries=3)
def run_phantom_buster_sales_navigator(self, launch_id: int) -> tuple[bool, str]:
    try:
        # Get Launch entry
        launch: PhantomBusterSalesNavigatorLaunch = PhantomBusterSalesNavigatorLaunch.query.get(launch_id)
        pb_sales_navigator: PhantomBusterSalesNavigatorConfig = PhantomBusterSalesNavigatorConfig.query.get(launch.sales_navigator_config_id)

        phantom_uuid = pb_sales_navigator.phantom_uuid
        phantom: PhantomBusterAgent = PhantomBusterAgent(phantom_uuid)
        if "id" not in phantom.get_agent_data():
            return False, "PhantomBuster agent has not been created yet"

        # Mark Launch entry as running
        launch.status = SalesNavigatorLaunchStatus.RUNNING
        launch.launch_date = datetime.utcnow()
        db.session.commit()

        # Update PhantomBuster agent's sales_navigator_url
        phantom.update_argument("searches", launch.sales_navigator_url)
        phantom.update_argument("numberOfProfiles", launch.scrape_count)

        # Launch PhantomBuster agent
        response = phantom.run_phantom()
        if response.status_code != 200:
            raise Exception("PhantomBuster agent failed to launch")
        result = response.json()

        # Get PhantomBuster agent's output container_id
        container_id = result.get("data", {}).get("containerId")
        if not container_id:
            raise Exception("PhantomBuster agent failed to launch. Result: {payload}".format(payload=result))

        # Update Launch entry
        launch.pb_container_id = container_id
        launch.status = SalesNavigatorLaunchStatus.RUNNING
        db.session.commit()

        return True, "PhantomBuster agent launched successfully"
    except Exception as e:
        # Mark launch as failed
        launch.status = SalesNavigatorLaunchStatus.FAILED
        launch.error_message = str(e)
        db.session.commit()

        # Retry
        self.retry(exc=e, countdown=5)
