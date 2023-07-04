from abc import ABC, abstractmethod
from redis import Redis
from typing import Tuple, Dict
from datetime import datetime
import json


class DatabaseError(Exception):
    """Class providing a basic db error.

    Args:
        message (str): Error message to be returned.
    """

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(f"Database Error: {message}")


class Database(ABC):
    """Abstract class for database providing the neccessary functions."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    @abstractmethod
    def is_running(self) -> None:
        """Check whether database is running.

        Raises:
            DatabaseError, if connection cannot be made.
        """
        pass

    @abstractmethod
    def get_server_startup_time(self) -> int:
        """Returns startup time of the server as POSIX timestamp."""
        pass

    @abstractmethod
    def set_server_startup_time(self, unixtime: float) -> None:
        """Sets startup time of the server as POSIX timestamp."""
        pass

    @abstractmethod
    def get_airspaces(self) -> Dict[str, Tuple]:
        """Returns Dictionary of airspaces in the form name: bounding_box."""
        pass

    @abstractmethod
    def set_airspaces(self, airspaces: Dict[str, Tuple]) -> None:
        """Saves airspace-dictionary in the form name: bounding_box."""
        pass

    @abstractmethod
    def get_total_carbon(self, airspace: str) -> float:
        """Returns total carbon emission value in airspace."""
        pass

    @abstractmethod
    def set_total_carbon(self, airspace: str, value: float) -> None:
        """Sets total carbon emission value in airspace."""
        pass

    @abstractmethod
    def store_hourly_carbon(self, airspace: str, value: Tuple[int, float]) -> None:
        """Stores the hourly carbon emission value in an airspace.

        Args:
            airspace (str): Name of the observed airspace.
            value (Tuple[int, float]): Tuple of time in seconds since epoch
                and carbon emission value.
        """
        pass


class RedisDatabase(Database):
    """Implementation of database functions with a redis Database."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(host, port)
        self.redis = Redis(host=host, port=port, db=0)

    def is_running(self) -> None:
        """Check whether redis is running.

        Raises:
            DatabaseError, if redis is not reachable.
        """
        try:
            self.redis.info()
        except Exception:
            raise DatabaseError("Redis Database not running.")

    def get_server_startup_time(self) -> int:
        """Returns startup time of the server as POSIX timestamp from Redis."""
        timestamp = self.redis.get("startup_time")
        return int(timestamp.decode()) if timestamp else 0

    def set_server_startup_time(self, startup_time: datetime) -> None:
        """Sets startup time of the server as POSIX timestamp from Redis."""
        self.redis.set("startup_time", int(startup_time.timestamp()))

    def get_airspaces(self) -> Dict[str, Tuple]:
        """Returns a dictionary of airspaces in the form name: bounding_box from Redis."""
        airspaces = self.redis.hgetall("airspaces")
        return {
            key.decode("utf-8"): tuple(map(float, value.decode("utf-8").split(",")))
            for key, value in airspaces.items()
        }

    def set_airspaces(self, airspaces: Dict[str, Tuple]) -> None:
        """Saves airspace-dictionary in the form name: bounding_box from Redis."""
        airspaces_str = {
            airspace_name: ",".join(str(coord) for coord in bounding_box)
            for airspace_name, bounding_box in airspaces.items()
        }
        self.redis.hmset("airspaces", airspaces_str)

    def get_total_carbon(self, airspace: str) -> float:
        """Return total carbon emmision of given airspace from redis."""
        total_value = self.redis.hget("total", airspace)
        return float(total_value.decode()) if total_value else 0.0

    def set_total_carbon(self, airspace: str, value: float) -> None:
        """Sets total carbon emission value in airspace."""
        self.redis.hset("total", airspace, value)

    def store_hourly_carbon(self, airspace: str, value: Tuple[int, float]) -> None:
        """Stores the hourly carbon emission value in an airspace."""
        record = {"time": value[0], "co2": value[1]}
        hourly_carbon_records_bytes = self.redis.hget("hourly", airspace)
        if hourly_carbon_records_bytes is None:
            self.redis.hset("hourly", airspace, json.dumps([record]))
            return

        hourly_carbon_records = json.loads(hourly_carbon_records_bytes.decode())
        hourly_carbon_records.append(record)
        print(f"Hourly Carbon - {airspace}: {hourly_carbon_records}")
        self.redis.hset("hourly", airspace, json.dumps(hourly_carbon_records))
