from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import time


# def print_date_time():
#     from src.client.services import create_client

#     print(time.strftime("%A, %d. %B %Y %I:%M:%S %p"))


scheduler = BackgroundScheduler()
# scheduler.add_job(func=print_date_time, trigger="interval", seconds=5)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())
