from typing import Optional

from src.voyager.services import withdraw_li_invite
from src.automation.models import ProcessQueue
from app import celery, db
from datetime import datetime

# Define what process types call what functions (with celery)
# - args are passed into the function from meta_data.args
PROCESS_TYPE_MAP = {
    "li_invite_withdraw": {
        'function': withdraw_li_invite,
        'priority': 10,
        'queue': None,
        'routing_key': None,
    }
}


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
    if not process_data: return False

    ### Read and use meta data here ###

    # Get args as dict from meta_data
    args = meta_data.get('args') if meta_data else {}
    if not args or not isinstance(args, dict): args = {}

    # Execute the function on the appropriate celery worker queue
    (process_data.get('function')).apply_async(
        kwargs=args,
        queue=process_data.get('queue', None),
        routing_key=process_data.get('routing_key', None),
        priority=process_data.get('priority', 1),
    )

    return True


def add_process_to_queue(type: str, meta_data: Optional[dict], execution_date: datetime):
    """ Adds an instance to the process queue
    
    Args:
        type (str): The type of process, must be an option in the PROCESS_TYPE_MAP
        meta_data (dict): Any meta data that is relevant for the process.
           - Values in the "args" entry is passed into the executed function
        execution_date: (datetime): The time in which the process will be executed

    Returns:
        ProcessQueue (dict): The added process queue as a dict
        or
        None, reason (str)
    """

    if not (type in PROCESS_TYPE_MAP):
        return None, 'Invalid process type'

    process = ProcessQueue(
        type=type,
        meta_data=meta_data,
        execution_date=execution_date,
    )
    db.session.add(process)
    db.session.commit()

    return process.to_dict()


def remove_process_from_queue(process_id: int):
    """ Removes a process from the process queue
    
    Args:
        process_id (int): The id of the process queue

    Returns:
        success (bool): Whether it was deleted or not
    """

    process: ProcessQueue = ProcessQueue.query.get(process_id)
    if not process: return False

    db.session.delete(process)
    db.session.commit()

    return True



    
