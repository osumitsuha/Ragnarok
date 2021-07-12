from objects.collections import Tokens, Channels, Matches
from events import bancho, osu, avatar  # dont remove
from lenhttp import LenHTTP, Request
from lib.database import Database
from objects.bot import Louise
from constants import commands  # dont remove
from objects import glob
from utils import log
import os
import sys

kwargs = {
    "logging": False,
}

glob.server = LenHTTP(("127.0.0.1", 8000), **kwargs)


@glob.server.before_serving()
async def startup():
    print(f"\033[94m{glob.title_card}\033[0m")

    glob.players = Tokens()
    glob.channels = Channels()
    glob.matches = Matches()

    for _path in (".data/avatars", ".data/replays", ".data/beatmaps"):
        if not os.path.exists(_path):
            log.warn(
                f"You're missing the folder {_path}! Don't worry we'll add it for you!"
            )

            os.makedirs(_path)

    log.info(f"Running Ragnarok on `{glob.domain}` (port: {glob.port})")

    log.info(".. Connecting to the database")

    glob.sql = Database()
    await glob.sql.connect(glob.config["mysql"])

    log.info("✓ Connected to the database!")

    log.info("... Connecting Louise to the server")

    if not await Louise.init():
        log.fail("✗ Couldn't find Louise in the database.")
        sys.exit()

    log.info("✓ Successfully connected Louise!")

    log.info("... Adding channels")

    async for channel in glob.sql.iterall(
        "SELECT name, description, public, staff, auto_join, read_only FROM channels"
    ):
        glob.channels.add_channel(channel)

    log.info("✓ Successfully added all avaliable channels")

    log.info("Finished up connecting to everything!")


@avatar.avatar.after_request()
@osu.osu.after_request()
async def after_request(req: Request):
    if req.resp_code == 404:
        lprint = log.error
    else:
        lprint = log.info

    if req.resp_code != 500:
        lprint(f"[{req.type}] {req.path} | {req.elapsed}")


@glob.server.add_middleware(500)
async def fivehundred(req: Request, tb: str):
    log.fail(f"An error occured on `{req.path}` | {req.elapsed}\n{tb}")

    return b""


glob.server.add_routers({bancho.bancho, avatar.avatar, osu.osu})
glob.server.start()
