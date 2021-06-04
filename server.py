from starlette.applications import Starlette
from events import bancho, osu, avatar
from lib.database import Database
from objects.bot import Louise
from objects import glob
from utils import log

async def startup():
    log.info("Starting up Atarashi...")
    log.info("Connecting to the database...")

    glob.sql = Database()
    await glob.sql.connect(glob.config["mysql"])

    log.info("Connected to the database!")

    log.info("Connecting Louise to the server...")
    await Louise.init()
    log.info("Connected Louise!")

    log.info("Adding channels...")

    async for channel in glob.sql.iterall("SELECT name, description, public, admin FROM channels"):
        log.info(f"Adding {channel['name']}")
        await glob.channels.add_channel(**channel)
        log.info(f"Successfully added {channel['name']}")

    log.info("Finished up connecting to everything!")

star = Starlette(routes=glob.registered_routes, on_startup=[startup])