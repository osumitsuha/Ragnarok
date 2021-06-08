from starlette.applications import Starlette
from events import bancho, osu, avatar # dont remove
from constants import commands # dont remove
from lib.database import Database
from objects.bot import Louise
from objects import glob
from utils import log
import os

async def startup():
    print(f"\033[94m{glob.title_card}")

    for _path in (".data/avatars", ".data/replays", 
                  ".data/beatmaps", ".data/storyboards"):
        if not os.path.exists(_path):
            log.warning(f"You're missing the folder {_path}! Don't worry we'll add it for you!")

            os.makedirs(_path)

    log.info(".. Connecting to the database")

    glob.sql = Database()
    await glob.sql.connect(glob.config["mysql"])

    log.info("✓ Connected to the database!")

    log.info("... Connecting Louise to the server")
    if not await Louise.init():
        log.error("✗ Couldn't find Louise in the database.")
        os.exit(1)
        
    log.info("✓ Successfully connected Louise!")

    log.info("... Adding channels")

    async for channel in glob.sql.iterall("SELECT name, description, public, staff, auto_join, read_only FROM channels"):
        await glob.channels.add_channel(**channel)

    log.info("✓ Successfully added all avaliable channels")

    log.info("Finished up connecting to everything!")

star = Starlette(routes=glob.registered_routes, on_startup=[startup])