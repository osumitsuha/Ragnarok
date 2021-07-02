from lenhttp import Request, Router
from objects import glob
import aiofiles
import os

glob.avatar = Router({f"a.{glob.domain}", f"127.0.0.1:{glob.port}"})

@glob.avatar.add_endpoint("/<uid>")
async def handle(req: Request, uid: str):
    if not uid:
        return 0

    if not uid.isnumeric():
        return "No."

    a_path = ".data/avatars/"

    if not os.path.exists(a_path + f"{uid}.png"):
        async with aiofiles.open(a_path + "0.png", "rb") as ava:
            avatar = await ava.read()
    else:
        async with aiofiles.open(a_path + f"{uid}.png", "rb") as ava:
            avatar = await ava.read()
        
    req.add_header("Content-Type", "image/png")

    return avatar
