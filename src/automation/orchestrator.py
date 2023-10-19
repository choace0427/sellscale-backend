from typing import Optional

from src.individual.services import add_individual_from_iscraper_cache, individual_similar_profile_crawler, upload_job_for_individual, convert_to_prospect
from src.voyager.services import withdraw_li_invite

from src.utils.datetime.dateutils import get_future_datetime
from src.automation.models import ProcessQueue
from app import celery, db
from datetime import datetime

###############################
# REGISTER PROCESS TYPES HERE #
###############################
# Define what process types call what functions (these functions need '@celery.task' decorator)
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
        "queue": 'icrawler',
        "routing_key": 'icrawler',
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
        "queue": 'individual-to-prospect',
        "routing_key": 'individual-to-prospect',
    },
}
###############################

@celery.task
def process_queue():
    """Main queue function, this is called every minute

    It executes any processes that are ready.
    """

    processes: list[ProcessQueue] = ProcessQueue.query.filter(
        ProcessQueue.execution_date < datetime.utcnow(),
    ).all()

    for process in processes:
        success = handle_process(process.type, process.meta_data)
        db.session.delete(process)

    db.session.commit()


def handle_process(type: str, meta_data: Optional[dict]) -> bool:
    """Execute the given process

    Reads meta data to get args or other information.
    Scheduled the appropriate celery worker to execute the function.

    Args:
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
        priority=process_data.get("priority", 1),
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
    )
    db.session.add(process)
    if commit:
        db.session.commit()

    return process.to_dict()


def remove_process_from_queue(process_id: int):
    """Removes a process from the process queue

    Args:
        process_id (int): The id of the process queue

    Returns:
        success (bool): Whether it was deleted or not
    """

    process: ProcessQueue = ProcessQueue.query.get(process_id)
    if not process:
        return False

    db.session.delete(process)
    db.session.commit()

    return True


def add_process_for_future(
    type: str,
    args: dict = {},
    months: int = 0,
    days: int = 0,
    minutes: int = 0,
    relative_time = datetime.utcnow(),
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
        execution_date=get_future_datetime(
            months, days, minutes, relative_time),
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
