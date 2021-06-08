from starlette.routing import Route
from starlette.responses import Response
from constants.packets import BanchoPackets
from typing import Callable
from functools import wraps
from objects import glob

def register(uri: str, methods: list = ["GET"]) -> Callable:
    def decorator(cb: Callable) -> Callable:
        glob.registered_routes.append(Route(uri, cb, methods=methods))

    return decorator

def register_event(packet: BanchoPackets, restricted: bool = False):
    def decorator(cb: Callable) -> Callable:
        glob.registered_packets.append({
            "func": cb, 
            "packet": packet, 
            "restricted": restricted
        })

    return decorator

def register_osu(route: str, method: str = "GET"):
    def decorator(cb: Callable) -> Callable:
        glob.registered_osu_routes.append({
            "func": cb, 
            "route": route, 
            "method": method
        })

    return decorator
