from typing import Callable
from objects import glob


def register_task() -> Callable:
    def wrapper(cb: Callable) -> None:
        glob.registered_tasks.append({"func": cb})

    return wrapper
