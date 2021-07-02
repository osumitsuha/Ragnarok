from lenhttp import Endpoint
from constants.packets import BanchoPackets
from typing import Callable
from objects import glob


def register_event(packet: BanchoPackets, restricted: bool = False):
    def decorator(cb: Callable) -> Callable:
        glob.registered_packets.append(
            {"func": cb, "packet": packet, "restricted": restricted}
        )

    return decorator


def register_osu(route: str, method: str = "GET"):
    def decorator(cb: Callable) -> Callable:
        glob.registered_osu_routes.append(
            {"func": cb, "route": route, "method": method}
        )

    return decorator

def register_task():
    def wrapper(cb):
        glob.registered_tasks.append(
            {"func": cb}
        )

    return wrapper
