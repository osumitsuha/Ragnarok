from constants.match import SlotStatus, ScoringType
from constants.player import Privileges
from constants.beatmap import Approved
from dataclasses import dataclass
from typing import TYPE_CHECKING
from objects.bot import Louise
from typing import Callable
from packets import writer
from typing import Union
from objects import glob
from utils import log
import asyncio
import random
import copy
import uuid
import time

if TYPE_CHECKING:
    from objects.player import Player
    from objects.channel import Channel


@dataclass
class Context:
    author: "Player"
    reciever: Union["Channel", "Player"]

    cmd: str
    args: list[str]


@dataclass
class Command:
    trigger: Callable
    cmd: str
    aliases: list[str]

    perms: Privileges
    doc: str
    hidden: bool


commands: list["Command"] = []
mp_commands: list["Command"] = []


def rmp_command(
    trigger: str,
    required_perms: Privileges = Privileges.USER,
    hidden: str = False,
    aliases: list[str] = [],
):
    def decorator(cb: Callable) -> Callable:
        cmd = Command(
            trigger=cb,
            cmd=trigger,
            aliases=aliases,
            perms=required_perms,
            doc=cb.__doc__,
            hidden=hidden,
        )

        mp_commands.append(cmd)

    return decorator


def register_command(
    trigger: str,
    required_perms: Privileges = Privileges.USER,
    hidden: str = False,
    aliases: list[str] = [],
):
    def decorator(cb: Callable) -> Callable:
        cmd = Command(
            trigger=cb,
            cmd=trigger,
            aliases=aliases,
            perms=required_perms,
            doc=cb.__doc__,
            hidden=hidden,
        )

        commands.append(cmd)

    return decorator


#
# Normal user commands
#


@register_command("help")
async def help(ctx: Context) -> str:
    """The help message"""

    if ctx.args:
        trigger = ctx.args[0]

        for key in commands:
            if key.cmd != trigger:
                continue

            if key.hidden:
                continue

            if not key.perms & ctx.author.privileges:
                continue

            return f"{glob.prefix}{key.cmd} | Needed privileges ~> {key.perms.name}\nDescription: {key.doc}"

    visible_cmds = [
        cmd.cmd
        for cmd in commands
        if not cmd.hidden and cmd.perms & ctx.author.privileges
    ]

    return "List of all commands.\n " + "|".join(visible_cmds)


@register_command("ping")
async def ping_command(ctx: Context) -> str:
    """Ping the server, to see if it responds."""

    return "PONG"


@register_command("roll")
async def roll(ctx: Context) -> str:
    """Roll a dice!"""

    x = 100

    if len(ctx.args) > 1:
        x = int(ctx.args[1])

    return f"{ctx.author.username} rolled {random.randint(0, x)} point(s)"


@register_command("last_np", hidden=True)
async def last_np(ctx: Context) -> str:
    if not ctx.author.last_np:
        return "No np."

    return ctx.author.last_np.full_title


@register_command("stats")
async def user_stats(ctx: Context) -> str:
    """Display a users stats both vanilla or relax."""

    if len(ctx.args) < 1:
        return "Usage: !stats <username>"

    if not (t := await glob.players.get_user_offline(ctx.args[0])):
        return "Player isn't online or couldn't be found in the database"

    relax = 0

    if len(ctx.args) == 2:
        if ctx.args[1] == "rx":
            relax = 1

    ret = await t.get_stats(relax)

    return (
        f"Stats for {t.username}:\n"
        f"PP: {ret['pp']} (#{ret['rank']})\n"
        f"Plays: {ret['playcount']} (lv{ret['level']})\n"
        f"Accuracy: {ret['level']}%"
    )


@register_command("verify", required_perms=Privileges.PENDING)
async def verify_with_key(ctx: Context) -> str:
    """Verify your account with our key system!"""

    if ctx.reciever[0] == "#":
        return "This command only works in BanchoBot's PMs."

    if not len(ctx.args) != 1:
        return "Usage: !verify <your beta key>"

    key = ctx.args[0]

    if not (
        key_info := await glob.sql.fetch(
            "SELECT id, beta_key, made FROM beta_keys WHERE beta_key = %s", (key)
        )
    ):
        return "Invalid key"

    if key_info["made"] >= time.time():
        asyncio.create_task(
            glob.sql.execute("DELETE FROM beta_keys WHERE id = %s", key_info["id"])
        )

        return "Expired key. (older than 7 days)"

    asyncio.create_task(
        glob.sql.execute(
            "UPDATE users SET privileges = %s WHERE id = %s",
            (Privileges.USER.value + Privileges.VERIFIED.value, ctx.author.id),
        )
    )

    asyncio.create_task(
        glob.sql.execute("DELETE FROM beta_keys WHERE id = %s", key_info["id"])
    )

    ctx.author.privileges = Privileges.USER + Privileges.VERIFIED
    ctx.author.enqueue(
        await writer.Notification(
            "Welcome to Ragnarok. You've successfully verified your account and gained beta access! If you see any bugs or anything unusal, please report it to one of the developers, through Github issues or Discord."
        )
    )

    log.info(f"{ctx.author.username} successfully verified their account with a key")

    return "Successfully verified your account."


#
# Multiplayer commands
#


@rmp_command("help")
async def multi_help(ctx: Context) -> str:
    """Multiplayer help command"""
    return "Not done yet."


@rmp_command("start")
async def start_match(ctx: Context) -> str:
    """Start the multiplayer when all players are ready or force start it."""
    if not (m := ctx.author.match):
        return

    if m.host != ctx.author.id:
        return

    if ctx.args:
        if ctx.args[0] == "force":
            for slot in m.slots:
                if slot.status & SlotStatus.OCCUPIED:
                    if slot.status != SlotStatus.NOMAP:
                        slot.status = SlotStatus.PLAYING
                        slot.p.enqueue(await writer.MatchStart(m))

            await m.enqueue_state(lobby=True)
            return "Starting match... Good luck!"

    if not all(
        slot.status == SlotStatus.READY
        for slot in m.slots
        if slot.status & SlotStatus.OCCUPIED
    ):
        return "All players aren't ready. The command for force starting a match is !mp start force"

    for slot in m.slots:
        if slot.status & SlotStatus.OCCUPIED:
            slot.status = SlotStatus.PLAYING

    m.in_progress = True

    m.enqueue(await writer.MatchStart(m))
    await m.enqueue_state()


@rmp_command("win", aliases=["wc"])
async def win_condition(ctx: Context) -> str:
    """Change win condition in a multiplayer match."""
    if not ((m := ctx.author.match) or ctx.author.match.host == ctx.author.id):
        return

    if not ctx.args:
        return f"Wrong usage. !multi {ctx.cmd} <score/acc/combo/sv2/pp>"

    if ctx.args[0] != "pp":
        old_scoring = copy.copy(m.scoring_type)
        m.scoring_type = ScoringType.find_value(ctx.args[0])

        await m.enqueue_state()
        return f"Changed win condition from {old_scoring.name.lower()} to {m.scoring_type.name.lower()}"

    m.scoring_type = ScoringType.SCORE  # force it to be score
    m.pp_win_condition = True

    await m.enqueue_state()
    return "Changed win condition to pp. THIS IS IN BETA AND CAN BE REMOVED ANY TIME."


#
# Staff commands
#


@register_command("kick", required_perms=Privileges.MODERATOR)
async def kick_user(ctx: Context) -> str:
    """Kick all players or just one player from the server."""

    if not ctx.args:
        return "Usage: !kick <username>"

    if ctx.args[0].lower() == "all":
        for p in glob.players.players[:]:
            if (p == ctx.author) or p.bot:
                continue

            await p.logout()

        return "Kicked every. single. user online."

    if not (t := await glob.players.get_user_offline(" ".join(ctx.args))):
        return "Player isn't online or couldn't be found in the database"

    await t.logout()
    t.enqueue(await writer.Notification("You've been kicked!"))

    return f"Successfully kicked {t.username}"


@register_command("restrict", required_perms=Privileges.ADMIN)
async def restrict_user(ctx: Context) -> str:
    """Restrict users from the server"""

    if ctx.reciever != "#staff":
        return "You can't do that here."

    if len(ctx.args) < 1:
        return "Usage: !restrict <username>"

    if not (t := await glob.players.get_user_offline(" ".join(ctx.args))):
        return "Player isn't online or couldn't be found in the database"

    if t.is_restricted:
        return "Player is already restricted? Did you mean to unrestrict them?"

    asyncio.create_task(
        glob.sql.execute(
            "UPDATE users SET privileges = privileges - 4 WHERE id = %s", (t.id)
        )
    )

    t.privileges -= Privileges.VERIFIED

    t.enqueue(
        await writer.Notification("An admin has set your account in restricted mode!")
    )

    return f"Successfully restricted {t.username}"


@register_command("unrestrict", required_perms=Privileges.ADMIN)
async def unrestrict_user(ctx: Context) -> str:
    """Unrestrict users from the server."""

    if ctx.reciever != "#staff":
        return "You can't do that here."

    if len(ctx.args) < 1:
        return "Usage: !unrestrict <username>"

    if not (t := await glob.players.get_user_offline(" ".join(ctx.args))):
        return "Player isn't online or couldn't be found in the database"

    if not t.is_restricted:
        return "Player isn't even restricted?"

    await glob.sql.execute(
        "UPDATE users SET privileges = privileges + 4 WHERE id = %s", (t.id)
    )

    t.privileges += Privileges.VERIFIED

    t.enqueue(await writer.Notification("An admin has unrestricted your account!"))

    return f"Successfully unrestricted {t.username}"


@register_command("bot", required_perms=Privileges.DEV)
async def bot_commands(ctx: Context) -> str:
    """Handle our bot ingame"""

    if not ctx.args:
        return f"{glob.bot.username.lower()}."

    if ctx.args[0] == "reconnect":
        if glob.players.get_user(1):
            return f"{glob.bot.username} is already connected."

        await Louise.init()

        return f"Successfully connected {glob.bot.username}."


@register_command("approve")
async def approve_map(ctx: Context) -> str:
    """Change the ranked status of beatmaps."""

    if not ctx.author.last_np:
        return "Please /np a map first."

    if ctx.author.last_np.hash_md5 in glob.beatmaps:
        _map = glob.beatmaps[ctx.author.last_np.hash_md5]
    else:
        _map = ctx.author.last_np

    if len(ctx.args) != 2:
        return "Usage: !approve <set/map> <rank/love/unrank>"

    if not ctx.args[0] in ("map", "set"):
        return "Invalid first argument (map or set)"

    if not ctx.args[1] in ("rank", "love", "unrank"):
        return "Invalid approved status (rank, love or unrank)"

    ranked_status = {
        "rank": Approved.RANKED,
        "love": Approved.LOVED,
        "unrank": Approved.PENDING,
    }[ctx.args[1]]

    if _map.approved == ranked_status.value:
        return f"Map is already {ranked_status.name}"

    set_or_map = ctx.args[0] == "map"

    await glob.sql.execute(
        "UPDATE beatmaps SET approved = %s "
        f"WHERE {'map_id' if set_or_map else 'set_id'} = %s LIMIT 1",
        (ranked_status.value, _map.map_id if set_or_map else _map.set_id),
    )

    resp = f"Successfully changed {_map.full_title}'s status, from {Approved(_map.approved).name} to {ranked_status.name}"

    if ctx.author.last_np.hash_md5 in glob.beatmaps:
        _map.approved = ranked_status + 1

    return resp


@register_command("key", required_perms=Privileges.ADMIN)
async def beta_keys(ctx: Context) -> str:
    """Create or delete keys."""

    if len(ctx.args) < 1:
        return "Usage: !key <create/delete> <name if create (OPTIONAL) / id if delete>"

    if ctx.args[0] == "create":
        if len(ctx.args) != 2:
            key = uuid.uuid4().hex

            asyncio.create_task(
                glob.sql.execute(
                    "INSERT INTO beta_keys VALUES (NULL, %s, %s)",
                    (key, time.time() + 432000),
                )
            )

            return f"Created key with the name {key}"

        key = ctx.args[1]

        asyncio.create_task(
            glob.sql.execute(
                "INSERT INTO beta_keys VALUES (NULL, %s, %s)",
                (key, time.time() + 432000),
            )
        )

        return f"Created key with the name {key}"

    elif ctx.args[0] == "delete":
        if len(ctx.args) != 2:
            return "Usage: !key delete <key id>"

        key_id = ctx.args[1]

        if not await glob.sql.fetch("SELECT 1 FROM beta_keys WHERE id = %s", (key_id)):
            return "Key doesn't exist"

        asyncio.create_task(
            glob.sql.execute("DELETE FROM beta_keys WHERE id = %s", (key_id))
        )

        return f"Deleted key {key_id}"

    return "Usage: !key <create/delete> <name if create (OPTIONAL) / id if delete>"


async def handle_commands(
    message: str, sender: "Player", reciever: Union["Channel", "Player"]
) -> None:
    if message[:6] == "!multi":
        message = message[7:]
        commands_set = mp_commands
    else:
        message = message[1:]
        commands_set = commands

    ctx = Context(
        author=sender,
        reciever=reciever,
        cmd=message.split(" ")[0].lower(),
        args=message.split(" ")[1:],
    )

    for command in commands_set:
        if ctx.cmd != command.cmd or not command.perms & ctx.author.privileges:
            if ctx.cmd not in command.aliases:
                continue

        return await command.trigger(ctx)
