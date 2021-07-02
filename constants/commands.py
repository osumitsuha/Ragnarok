from constants.player import Privileges
from constants.beatmap import Approved
from constants.match import SlotStatus
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
import uuid
import time

if TYPE_CHECKING:
    from objects.player import Player
    from objects.channel import Channel

@dataclass
class Context:
    author: 'Player'
    reciever: Union['Channel', 'Player']
    
    cmd: str
    args: list[str]

@dataclass
class Command:
    trigger: Callable
    cmd: str
    
    perms: Privileges
    doc: str
    hidden: bool

commands: list['Command'] = []
mp_commands: list['Command'] = []

def rmp_command(trigger: str, required_perms=Privileges.USER, hidden=False):
    def decorator(cb: Callable) -> Callable:
        cmd = Command(
            trigger=cb,
            cmd=trigger,
            perms=required_perms,
            doc=cb.__doc__,
            hidden=hidden
        )

        mp_commands.append(cmd)

    return decorator

def register_command(trigger: str, required_perms=Privileges.USER, hidden=False):
    def decorator(cb: Callable) -> Callable:
        cmd = Command(
            trigger=cb,
            cmd=trigger,
            perms=required_perms,
            doc=cb.__doc__,
            hidden=hidden
        )

        commands.append(cmd)

    return decorator

# 
# Normal user commands
#

@register_command("help")
async def help(ctx: Context) -> str:
    """ The help message """
    
    if ctx.args:
        trigger = ctx.args[0]

        for key in glob.registered_commands:
            key_trigger = key.cmd[len(glob.prefix):]

            if key_trigger != trigger:
                continue

            if key.hidden:
                continue

            if not key.perms & ctx.author.privileges:
                continue

            return key.doc

    visible_cmds = [cmd.cmd for cmd in glob.registered_commands if not cmd.hidden and cmd.perms & ctx.author.privileges]

    return "List of all commands.\n " + "|".join(visible_cmds)


@register_command("ping")
async def ping_command(ctx: Context) -> str:
    """ A command that pings the server, to see if it responds. """

    return "PONG"


@register_command("roll")
async def roll(ctx: Context) -> str:
    """ A command that rolls a number to 0 to `x`.
        arg: `x` | 100 (default)
            [OPTIONAL] Sets the `x` variable.
    """

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
    """ A command that displays `username`s stats for the choosen gamemode.
        arg: `username`
            The users username

        arg: `rx/vn` | `vn` (default)
            [OPTIONAL] Choose between, if you want the relax stats or vanilla stats.
    """

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
    """ A command that verifies your account, with the help of a key.
        arg: `key`
            The key used to get the account verified.
    """

    if ctx.reciever[0] == "#":
        return "This command only works in BanchoBot's PMs."

    if not len(ctx.args) != 1:
        return "Usage: !verify <your beta key>"

    key = ctx.args[0]

    if not (key_info := await glob.sql.fetch("SELECT id, beta_key, made FROM beta_keys WHERE beta_key = %s", (key))):
        return "Invalid key"

    if key_info["made"] >= time.time():
        asyncio.create_task(glob.sql.execute("DELETE FROM beta_keys WHERE id = %s", key_info["id"]))

        return "Expired key. (older than 7 days)"

    asyncio.create_task(glob.sql.execute(
        "UPDATE users SET privileges = %s WHERE id = %s",
        (Privileges.USER.value + Privileges.VERIFIED.value, ctx.author.id)
    ))

    asyncio.create_task(glob.sql.execute("DELETE FROM beta_keys WHERE id = %s", key_info["id"]))

    ctx.author.privileges = Privileges.USER + Privileges.VERIFIED
    ctx.author.enqueue(await writer.Notification("Welcome to Ragnarok. You've successfully verified your account and gained beta access! If you see any bugs or anything unusal, please report it to one of the developers, through Github issues or Discord."))

    log.info(f"{ctx.author.username} successfully verified their account with a key")

    return "Successfully verified your account."

#
# Multiplayer commands
#

@rmp_command("help")
async def multi_help(ctx: Context) -> str:
    return "Not done yet."

@rmp_command("start")
async def force_start_match(ctx: Context) -> str:
    if not (m := ctx.author.match):
        return 

    if ctx.author.id != m.host:
        return

    if ctx.args:
        if ctx.args[0] == "force":
            for slot in m.slots:
                if (ss := slot.status) & SlotStatus.OCCUPIED:
                    if ss != SlotStatus.NOMAP:
                        ss = SlotStatus.PLAYING
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

    m.enqueue(await writer.MatchStart(m))
    await m.enqueue_state()

# 
# Staff commands
#

@register_command("kick", required_perms=Privileges.MODERATOR)
async def kick_user(ctx: Context) -> str:
    """ A command that kicks the users from the server.
        arg: `username`
            The users username.
    """

    if len(ctx.args) < 1:
        return "Usage: !kick <username>"

    if not (t := await glob.players.get_user_offline(" ".join(ctx.args))):
        return "Player isn't online or couldn't be found in the database"

    await t.logout()
    t.enqueue(await writer.Notification("You've been kicked!"))

    return f"Successfully kicked {t.username}"


@register_command("restrict", required_perms=Privileges.ADMIN)
async def restrict_user(ctx: Context) -> str:
    """ A command that restricts the user from the server.
        arg: `username`
            The users username.
    """

    if ctx.reciever != "#staff":
        return "You can't do that here."

    if len(ctx.args) < 1:
        return "Usage: !restrict <username>"

    if not (t := await glob.players.get_user_offline(" ".join(ctx.args))):
        return "Player isn't online or couldn't be found in the database"

    if t.is_restricted:
        return "Player is already restricted? Did you mean to unrestrict them?"

    asyncio.create_task(glob.sql.execute(
        "UPDATE users SET privileges = privileges - 4 WHERE id = %s", (t.id)
    ))

    t.privileges -= Privileges.VERIFIED

    t.enqueue(
        await writer.Notification("An admin has set your account in restricted mode!")
    )

    return f"Successfully restricted {t.username}"

@register_command("unrestrict", required_perms=Privileges.ADMIN)
async def unrestrict_user(ctx: Context) -> str:
    """ A command that unrestricts the user from the server.
        arg: `username`
            The users username.
    """

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

    t.enqueue(
        await writer.Notification("An admin has unrestricted your account!")
    )

    return f"Successfully unrestricted {t.username}"


@register_command("bot", required_perms=Privileges.DEV)
async def bot_commands(ctx: Context) -> str:
    """ A command that handles problems with the bot (Louise).
        arg: `reconnect`
            Reconnects the bot, if it's not connected to the server.
    """

    if len(ctx.args) < 1:
        return f"{glob.bot.username.lower()}."

    if ctx.args[0] == "reconnect":
        if await glob.players.get_user(1):
            return f"{glob.bot.username} is already connected."

        await Louise.init()

        return f"Successfully connected {glob.bot.username}."


@register_command("approve")
async def approve_map(ctx: Context) -> str:
    """ A command that changes a beatmaps ranked status.
        arg: `set/map`
            Choose between, if you want to change a single beatmaps status or the whole sets status.

        arg: `rank/love/unrank`
            Choose between, which status you want it to be updated to.
    """

    if not ctx.author.last_np:
        return "Please /np a map first."
    
    if (ctx.author.last_np.hash_md5 in glob.beatmaps):
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
    """ A command for creating new keys or deleting.
        arg: `create/delete` 
            Choose between, if you want to create a new key or delete an old key.

        arg: 
            `key` | `uuid.uuid()` (default):
                [OPTIONAL] *This is the second argument, only if you choose to create on the first argument.*
                [OPTIONAL] The keys name.

            `id`:
                *This is the second argument, only if you choose to delete on the first argument.*
                The id used to get the key, you want to delete.

    """

    if len(ctx.args) < 1:
        return "Usage: !key <create/delete> <name if create (OPTIONAL) / id if delete>"

    if ctx.args[0] == "create":
        if len(ctx.args) != 2:
            key = uuid.uuid4().hex

            asyncio.create_task(glob.sql.execute("INSERT INTO beta_keys VALUES (NULL, %s, %s)", (key, time.time() + 432000)))

            return f"Created key with the name {key}"

        key = ctx.args[1]

        asyncio.create_task(glob.sql.execute("INSERT INTO beta_keys VALUES (NULL, %s, %s)", (key, time.time() + 432000)))

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


async def handle_commands(message: str, sender: 'Player', reciever: Union['Channel', 'Player']) -> None:
    if message[:6] == "!multi":
        message = message[7:]
        commands_set = mp_commands
    else:
        message = message[1:]
        commands_set = commands

    log.info(commands_set)
    log.info(message)

    ctx = Context(author=sender, reciever=reciever, cmd=message.split(" ")[0].lower(), args=message.split(" ")[1:])

    for command in commands_set:
        if (
            ctx.cmd != command.cmd or
            not command.perms & ctx.author.privileges
        ):
            continue

        return await command.trigger(ctx)