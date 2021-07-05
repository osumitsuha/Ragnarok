from lenhttp import Request, Router
from objects import glob
import aiofiles
import os

avatar = Router({f"a.{glob.domain}", f"127.0.0.1:{glob.port}"})
a_path = ".data/avatars/"

@avatar.add_endpoint("/<uid>")
async def handle(req: Request, uid: str) -> bytes:
    if (
        not uid or
        not uid.isnumeric()
    ):
        return 0

    if not os.path.exists(a_path + f"{uid}.png"):
        async with aiofiles.open(a_path + "0.png", "rb") as ava:
            avatar = await ava.read()
    else:
        async with aiofiles.open(a_path + f"{uid}.png", "rb") as ava:
            avatar = await ava.read()

    req.add_header("Content-Type", "image/png")

    return avatar
