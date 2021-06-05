from constants.privileges import Privileges 
from objects.bot import Louise
from packets import writer
from typing import Callable
from objects import glob
from objects.player import Player
from utils import log

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
        return "Who to kick?"

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
        return "Who to restrict?"

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
        return "Who to unrestrict?"

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