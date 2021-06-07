from constants.privileges import Privileges 
from objects.bot import Louise
from packets import writer
from typing import Callable
from objects import glob
from objects.player import Player
from utils import log
import random

def register_command(cmd: str, required_perms = Privileges.USER):
    def decorator(cb: Callable) -> Callable:
        glob.registered_commands.append({
            "trigger": cb, 
            "cmd": cmd, 
            "required_perms": required_perms
        })

    return decorator

@register_command("ping")
async def ping_command(p, chan, message):
    # usage: !ping

    return "PONG"

@register_command("kick")
async def kick_user(p, chan, message):
    # usage: !kick <username>
    
    args = message.split(" ")[1:]

    if len(args) < 1:
        return "Usage: !kick <username>"

    if not (t := await glob.players.get_user(" ".join(args))):
        return "Player isn't online, or couldn't be found."

    await t.logout()
    t.enqueue(await writer.Notification("You've been kicked!"))

    return f"Successfully kicked {t.username}"

@register_command("restrict")
async def restrict_user(p, chan, message):
    # usage: !restrict <username>

    if chan != "#staff":
        return "You can't do that here."
    
    args = message.split(" ")[1:]

    if len(args) < 1:
        return "Usage: !restrict <username>"

    if not (t := await glob.players.get_user(" ".join(args))):
        # if can't be found in cache thingy
        # try getting it from database
        if not (d := await glob.sql.fetch("SELECT username, id, privileges, passhash FROM users WHERE username = %s", (" ".join(args)))):
            return "Player couldn't be found in the database"

        d["ip"] = "127.0.0.1" # locallhost cause ip is needed 

        t = Player(**d)

    if t.is_restricted:
        return "Player is already restricted? Did you mean to unrestrict them?"

    await glob.sql.execute("UPDATE users SET privileges = privileges - 4 WHERE id = %s", (t.id))
    t.enqueue(await writer.Notification("An admin has set your account in restricted mode!"))

    return f"Successfully restricted {t.username}"

@register_command("unrestrict")
async def unrestrict_user(p, chan, message):
    # usage: !unrestrict <username>

    if chan != "#staff":
        return "You can't do that here."
    
    args = message.split(" ")[1:]

    if len(args) < 1:
        return "Usage: !unrestrict <username>"

    if not (t := await glob.players.get_user(" ".join(args))):
        # if can't be found in cache thingy
        # try getting it from database
        if not (d := await glob.sql.fetch("SELECT username, id, privileges, passhash FROM users WHERE username = %s", (" ".join(args)))):
            return "Player couldn't be found in the database"

        d["ip"] = "127.0.0.1" # locallhost cause ip is needed 

        t = Player(**d)

    if not t.is_restricted:
        return "Player isn't even restricted?"

    await glob.sql.execute("UPDATE users SET privileges = privileges + 4 WHERE id = %s", (t.id))

    return f"Successfully unrestricted {t.username}"

@register_command("louise")
async def louise_commands(p, chan, message):
    # usage: !louise <action>

    args = message.split(" ")[1:]

    if len(args) < 1:
        return "louise."

    if args[0] == "reconnect":
        if await glob.players.get_user_by_id(1):
            return "Louise is already connected."

        await Louise.init()

        return "Successfully connected Louise."

@register_command("roll")
async def roll(p, chan, message):
    # usage: !roll

    return f"{p.username} rolled {random.randint(0, 100)} point(s)"

@register_command("stats")
async def user_stats(p, chan, message):
    # usage: !stats <username> <rx/vn>

    args = message.split(" ")[1:]

    if len(args) < 2:
        return "Usage: !stats <username> <rx/vn>"

    if not (t := await glob.players.get_user(args[0])):
        # if can't be found in cache thingy
        # try getting it from database
        if not (d := await glob.sql.fetch("SELECT username, id, privileges, passhash FROM users WHERE username = %s", (args[0]))):
            return "Player couldn't be found in the database"

        d["ip"] = "127.0.0.1" # locallhost cause ip is needed 

        t = Player(**d)

    relax = 0

    if args[1] == "rx":
        relax = 1

    ret = await t.get_stats(relax)

    return f"Stats for {t.username}:\n" \
           f"PP: {ret['pp']} (#{ret['rank']})\n" \
           f"Plays: {ret['playcount']} (lv{ret['level']})\n" \
           f"Accuracy: {ret['level']}%"