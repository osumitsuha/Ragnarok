from starlette.routing import Route
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

def check_auth(u: str, pw: str):
    def decorator(cb: Callable) -> Callable:
        @wraps(cb)
        async def wrapper(req, *args, **kwargs):
            # doesn't work properly
            # if not await glob.players.get_user(u):
            #     log.info("login error")
            #     return Response("")

            return await cb(req, *args, **kwargs)

        return wrapper

    return decorator
