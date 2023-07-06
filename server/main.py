import schedule
import time
import configparser
import uvicorn
from threading import Thread
from datetime import datetime
from multiprocessing import Process
from typing import Callable, Tuple, Optional, List
from queue import Queue
from argparse import ArgumentParser

from opensky_network import get_states
from carbon_computation import CarbonComputation
from server_api import FastAPIWithDatabase
from database import DatabaseError, RedisDatabase

API_HOST = "127.0.0.1"
API_PORT = 8000
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379

db = RedisDatabase(host=REDIS_HOST, port=REDIS_PORT)


class Worker(Thread):
    """Class to represent a worker thread managing a job queue."""

    def __init__(self) -> None:
        super().__init__()
        self.jobqueue: Queue = Queue()

    def run(self) -> None:
        """Execute all incoming jobs in the job queue."""
        while 1:
            try:
                job_func = self.jobqueue.get()
                job_func()
                self.jobqueue.task_done()
            except KeyboardInterrupt:
                break


def main() -> None:
    """Entry point of the application."""
    parser = ArgumentParser()
    parser.add_argument(
        "--config", type=str, help="Path to the configuration file", default="config.ini"
    )
    args = parser.parse_args()

    config_path = args.config

    # Read credentials from config file
    usernames = {}
    passwords = {}

    config = configparser.ConfigParser()
    config.read(config_path)

    for section in config.sections():
        if "username" in config[section] and "password" in config[section]:
            usernames[section] = config[section]["username"]
            passwords[section] = config[section]["password"]

    # Connect to Redis Database
    try:
        db.is_running()
    except DatabaseError:
        raise RuntimeError("Database connection failed.")

    # Specify bounding boxes for airspaces to be watched
    bounding_boxes = {
        "berlin": (52.3418234221, 13.0882097323, 52.6697240587, 13.7606105539),
        "paris": (48.753020, 2.138901, 48.937837, 2.493896),
        "london": (51.344500, -0.388934, 51.643400, 0.194758),
        "madrid": (40.312817, -3.831991, 40.561061, -3.524374),
    }
    db.set_airspaces(bounding_boxes)

    # Save current time as server startup time
    db.set_server_startup_time(datetime.now())

    # Initilize server carbon computations
    try:
        worker_threads = create_carbon_computer_workers(
            bounding_boxes, usernames, passwords, "minutes", 1
        )

        for worker_thread in worker_threads:
            worker_thread.start()

        # start the first carbon caclulation job now instead of waiting 1 minute
        for job in schedule.get_jobs("calculate-carbon"):
            job.run()

        # Start the server api in a seperate process
        api_process = Process(target=run_fastapi)
        api_process.start()

        # call opensky api every (1 + calculation time) minute(s)
        while True:
            schedule.run_pending()
            time.sleep(1)
    finally:
        api_process.terminate()
        api_process.join()


def run_fastapi() -> None:
    """Run the FastAPI application in a separate process."""
    app = FastAPIWithDatabase(db, host=API_HOST, port=API_PORT)
    uvicorn.run(app.app, host=API_HOST, port=API_PORT)


def create_update_total_co2_emission_job(
    username: str, password: str, carbon_computer: CarbonComputation
) -> Callable:
    """Creates a closure for the update_total_co2_emission_job function.

    This function takes a `username`, `password`, and `carbon_computer` as arguments
    and returns a closure that encapsulates these arguments. The closure, when invoked,
    calls the `update_total_co2_emission_job` function with the stored arguments.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.
        carbon_computer (CarbonComputation): Class instance to handle the computation
            of carbon emission in specific airspace.

    Returns:
        function (Callable): A lambda function that will call the
            update_total_co2_emission_job function with the stored arguments.
    """
    arguments = (username, password, carbon_computer)
    return lambda args=arguments: update_total_co2_emission_job(*args)


def create_carbon_computer_workers(
    bounding_boxes: dict[str, Tuple[float, float, float, float]],
    usernames: dict[str, str],
    passwords: dict[str, str],
    metric_time: str,
    interval: int,
) -> List[Worker]:
    """Creates worker threads for each city.

    Args:
        bounding_boxes (dict[str, Tuple]): A dictionary of bounding boxes of the
            watched airspace.
        usernames (dict[str, str]): A dictionary of usernames for authentication.
        passwords (dict[str, str]): A dictionary of passwords for authentication.
        carbon_computer (CarbonComputation): Class instance to handle the computation
            of carbon emission in specific airspace.
        metric_time (str): The measure of time intervals. Can be seconds,
            minutes, hours, days or weeks.
        interval (int): The interval at which the scheduled job should be executed.

    Returns:
        List[Worker]: List of worker threads to be started.
    """

    def schedule_co2_tracking(
        worker: Worker, job_func: Callable, metric_time: str, interval: int
    ) -> None:
        time_mapping = {
            "seconds": schedule.every(interval).seconds,
            "minutes": schedule.every(interval).minutes,
            "hours": schedule.every(interval).hours,
            "days": schedule.every(interval).days,
            "weeks": schedule.every(interval).weeks,
        }

        schedule_func = time_mapping.get(metric_time)
        if schedule_func:
            schedule_func.do(worker.jobqueue.put, job_func).tag("calculate-carbon")
        else:
            print("Invalid metric_time")

    worker_threads = []
    for city, bounding_box in bounding_boxes.items():
        username: Optional[str] = usernames.get(city)
        password: Optional[str] = passwords.get(city)
        if username and password:
            carbon_computer = CarbonComputation(city, bounding_box)
            username_not_none: str = username
            password_not_none: str = password
            worker_thread = Worker()
            carbon_computer_job_func = create_update_total_co2_emission_job(
                username_not_none, password_not_none, carbon_computer
            )
            schedule_co2_tracking(
                worker_thread,
                carbon_computer_job_func,
                metric_time,
                interval,
            )
            schedule.every(1).hours.do(store_hourly_co2_emission_job, carbon_computer)

            # create worker thread for every city
            worker_thread.daemon = True
            worker_threads.append(worker_thread)
        else:
            print(f"Missing credentials for {city}. Skipping...")

    return worker_threads


def update_total_co2_emission_job(
    username: str, password: str, carbon_computer: CarbonComputation
) -> None:
    """Wrapper function for updating the total co2 emission.

    Should be executed as a job by the schedule library.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.
        carbon_computer (CarbonComputation): Class instance to handle the computation
            of carbon emission in specific airspace.
    """
    response = get_states(username, password, carbon_computer.bounding_box)

    # Compute new emission (response["states"] can be null)
    if response is not None and response["states"] is not None:
        new_emission = carbon_computer.get_co2_emission(
            response["states"], response["time"]
        )
        print(f"New emission in {carbon_computer.airspace_name}: {new_emission}")

        # Update total emission
        total_emission = db.get_total_carbon(carbon_computer.airspace_name) + new_emission
        print(f"Total emission in {carbon_computer.airspace_name}: {total_emission}")
        db.set_total_carbon(carbon_computer.airspace_name, total_emission)


def store_hourly_co2_emission_job(carbon_computer: CarbonComputation) -> None:
    """Stores the hourly carbon emission value in an airspace to a database.

    Args:
        carbon_computer (CarbonComputation): Class instance to handle the computation
            of carbon emission in specific airspace.
    """
    total_value = db.get_total_carbon(carbon_computer.airspace_name)
    db.set_carbon_timestamp(carbon_computer.airspace_name, datetime.now(), total_value)


if __name__ == "__main__":
    main()
