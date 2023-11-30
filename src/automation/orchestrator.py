from typing import Optional

from src.smartlead.services import sync_prospect_with_lead, sync_email_warmings
from src.warmup_snapshot.services import set_warmup_snapshot_for_sdr

from src.triggers.services import trigger_runner

from src.prospecting.services import generate_prospect_upload_report
from src.email_scheduling.services import populate_email_messaging_schedule_entries

from src.individual.services import (
    add_individual_from_iscraper_cache,
    individual_similar_profile_crawler,
    upload_job_for_individual,
    convert_to_prospect,
)
from src.voyager.services import withdraw_li_invite

from src.utils.datetime.dateutils import get_future_datetime
from src.automation.models import ProcessQueue, ProcessQueueStatus
from app import celery, db
from datetime import datetime, timedelta

from sqlalchemy import or_, and_

###############################
# REGISTER PROCESS TYPES HERE #
###############################
# Define what process types call what functions (these functions need '@celery.task' decorator)
# - function must return a boolean for success or failure
# - args are passed into the function from meta_data.args
PROCESS_TYPE_MAP = {
    "li_invite_withdraw": {
        "function": withdraw_li_invite,
        "priority": 10,
        "queue": None,
        "routing_key": None,
    },
    "add_individual_from_iscraper_cache": {
        "function": add_individual_from_iscraper_cache,
        "priority": 10,
        "queue": None,
        "routing_key": None,
    },
    "run_icrawler": {
        "function": individual_similar_profile_crawler,
        "priority": 10,
        "queue": "icrawler",
        "routing_key": "icrawler",
    },
    "upload_job_for_individual": {
        "function": upload_job_for_individual,
        "priority": 10,
        "queue": None,
        "routing_key": None,
    },
    "convert_to_prospect": {
        "function": convert_to_prospect,
        "priority": 10,
        "queue": "individual-to-prospect",
        "routing_key": "individual-to-prospect",
    },
    "populate_email_messaging_schedule_entries": {
        "function": populate_email_messaging_schedule_entries,
        "priority": 1,
        "queue": "email_scheduler",
        "routing_key": "email_scheduler",
    },
    "generate_prospect_upload_report": {
        "function": generate_prospect_upload_report,
        "priority": 10,
        "queue": None,
        "routing_key": None,
    },
    "set_warmup_snapshot_for_sdr": {
        "function": set_warmup_snapshot_for_sdr,
        "priority": 10,
        "queue": None,
        "routing_key": None,
    },
    "sync_prospect_with_lead": {
        "function": sync_prospect_with_lead,
        "priority": 10,
        "queue": None,
        "routing_key": None,
    },
    "sync_email_warmings": {
        "function": sync_email_warmings,
        "priority": 10,
        "queue": None,
        "routing_key": None,
    },
    "trigger_runner": {
        "function": trigger_runner,
        "priority": 10,
        "queue": None,
        "routing_key": None,
    },
}
###############################


@celery.task
def process_queue():
    """Main queue function, this is called every minute

    It executes any processes that are ready.
    """
    now = datetime.utcnow()
    wait_time = now - timedelta(
        hours=1
    )  # The stale time for a process to be considered stuck

    # Scenarios:
    # 1. Process is QUEUED (or RETRY) and is ready to be executed
    # 2. Process is IN_PROGRESS but has been executing for more than 1 hour (it is stuck)
    processes: list[ProcessQueue] = ProcessQueue.query.filter(
        or_(
            and_(
                ProcessQueue.execution_date < now,
                or_(
                    ProcessQueue.status == ProcessQueueStatus.QUEUED,
                    ProcessQueue.status == ProcessQueueStatus.RETRY,
                    ProcessQueue.status == None,
                ),
            ),
            and_(
                ProcessQueue.executed_at < wait_time,
                ProcessQueue.status == ProcessQueueStatus.IN_PROGRESS,
            ),
        )
    ).all()

    for process in processes:
        process.executed_at = now
        process.status = ProcessQueueStatus.IN_PROGRESS
        handle_process(process.id, process.type, process.meta_data)

    db.session.commit()


def handle_process(process_id: int, type: str, meta_data: Optional[dict]) -> bool:
    """Execute the given process

    Reads meta data to get args or other information.
    Scheduled the appropriate celery worker to execute the function.

    Args:
        process_id (int): The id of the process queue
        type (str): The process type
        meta_data (dict): Any meta data for the process

    Returns:
        success (bool): Whether it was scheduled to execute or not
    """

    process_data = PROCESS_TYPE_MAP.get(type)
    if not process_data:
        return False

    ### Read and use meta data here ###

    # Get args as dict from meta_data
    args = meta_data.get("args") if meta_data else {}
    if not args or not isinstance(args, dict):
        args = {}

    # Execute the function on the appropriate celery worker queue
    (process_data.get("function")).apply_async(
        kwargs=args,
        queue=process_data.get("queue", None),
        routing_key=process_data.get("routing_key", None),
        priority=process_data.get("priority", 5),
        link=remove_process_from_queue.s(process_id),
    )

    return True


def add_process_to_queue(
    type: str, meta_data: Optional[dict], execution_date: datetime, commit: bool = True
):
    """Adds an instance to the process queue

    Args:
        type (str): The type of process, must be an option in the PROCESS_TYPE_MAP
        meta_data (dict): Any meta data that is relevant for the process.
           - Values in the "args" entry is passed into the executed function
        execution_date: (datetime): The time in which the process will be executed
        commit: (bool, optional): Whether to commit the process to the database or not

    Returns:
        ProcessQueue (dict): The added process queue as a dict
        or
        None, reason (str)
    """

    if not (type in PROCESS_TYPE_MAP):
        return None, "Invalid process type"

    process = ProcessQueue(
        type=type,
        meta_data=meta_data,
        execution_date=execution_date,
        status=ProcessQueueStatus.QUEUED,
    )
    db.session.add(process)
    if commit:
        db.session.commit()

    return process.to_dict()


@celery.task
def remove_process_from_queue(result: list, process_id: int):
    """Removes a process from the queue after it has been executed, depending on the result

    Args:
        result (list): The result of the executed function
        process_id (int): The id of the process queue

    Returns:
        success (bool): Whether it was deleted or not
    """
    process: ProcessQueue = ProcessQueue.query.get(process_id)
    if not process:
        return False

    # If the type is not a list, then this system wasn't used correctly.
    # For the time being, we will delete the process and raise an exception.
    if type(result) is not list:
        job = process.type

        db.session.delete(process)
        db.session.commit()
        raise Exception(
            f"Process return value was not correct, result was not a list. Function: {job}"
        )

    # Make sure that the first element of the list is a boolean
    result = result[0]
    if type(result) is not bool:
        job = process.type

        db.session.delete(process)
        db.session.commit()
        raise Exception(
            f"Process return value was not correct. Tuple's first value was not a boolean. Function: {job}"
        )

    if result:
        db.session.delete(process)
        db.session.commit()
    else:
        process.status = ProcessQueueStatus.RETRY
        db.session.commit()

    return True


def add_process_for_future(
    type: str,
    args: dict = {},
    months: int = 0,
    days: int = 0,
    minutes: int = 0,
    relative_time=datetime.utcnow(),
    commit: bool = True,
):
    """Adds an instance to the process queue

    Args:
        type (str): The type of process, must be an option in the PROCESS_TYPE_MAP
        args (dict, kwargs): Args that are passed into the function
        months: (int): Number of months until execution
        days: (int): Number of days until execution
        minutes: (int): Number of minutes until execution
        relative_time: (datetime): The time in which the future time is relative to
        commit: (bool, optional): Whether to commit the process to the database or not

    Returns:
        ProcessQueue (dict): The added process queue as a dict
        or
        None, reason (str)
    """

    return add_process_to_queue(
        type=type,
        meta_data={"args": args},
        execution_date=get_future_datetime(months, days, minutes, relative_time),
        commit=commit,
    )


def add_process_list(
    type: str,
    args_list: list[dict] = [],
    chunk_size: int = 10,
    init_wait_days: int = 0,
    init_wait_minutes: int = 0,
    chunk_wait_days: int = 0,
    chunk_wait_minutes: int = 0,
    buffer_wait_days: int = 0,
    buffer_wait_minutes: int = 0,
    append_to_end: bool = False,
):
    """Queues up a series of processes to be executed over a set amount of time

    Args:
        type (str): The type of process, must be an option in the PROCESS_TYPE_MAP
        args_list (list[dict], list[kwargs]): List of all args that will be executed.
            - Each arg entry is an individual process and executed function
        chunk_size: (int): Maximum number of args (processes) to be called at once at a time
        init_wait_days: (int): Initial onset number of days to wait before starting these executions
        init_wait_minutes: (int): Initial onset number of minutes to wait before starting these executions
        chunk_wait_days: (int): Number of days to wait in between each process chunk
        chunk_wait_minutes: (int): Number of minutes to wait in between each process chunk
        buffer_wait_days: (int): Number of days to wait in between each process in a chunk
        buffer_wait_minutes: (int): Number of minutes to wait in between each process in a chunk
        append_to_end: (bool): Whether to append the processes to the end of the queue or not (based on execution date)

    Returns:
        list[ProcessQueue] (list[dict]): List of queued process
    """

    start_time = datetime.utcnow()
    if append_to_end:
        last_process: ProcessQueue = (
            ProcessQueue.query.filter_by(type=type)
            .order_by(ProcessQueue.execution_date.desc())
            .first()
        )
        if last_process:
            start_time = last_process.execution_date

    processes = []

    chunks = [
        args_list[i : i + chunk_size] for i in range(0, len(args_list), chunk_size)
    ]

    total_wait_days = init_wait_days
    total_wait_minutes = init_wait_minutes
    for chunk in chunks:
        for i, args in enumerate(chunk):
            process = add_process_for_future(
                type=type,
                args=args,
                months=0,
                days=total_wait_days + (buffer_wait_days * i),
                minutes=total_wait_minutes + (buffer_wait_minutes * i),
                relative_time=start_time,
                commit=False,
            )
            processes.append(process)
        total_wait_days += chunk_wait_days
        total_wait_minutes += chunk_wait_minutes

    db.session.commit()
    return processes
