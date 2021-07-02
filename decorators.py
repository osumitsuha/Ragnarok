from lenhttp import Endpoint
from constants.packets import BanchoPackets
from typing import Callable
from objects import glob



def register_task():
    def wrapper(cb):
        glob.registered_tasks.append(
            {"func": cb}
        )

    return wrapper
