from constants.privileges import Privileges 
from objects.bot import Louise
from packets import writer
from typing import Callable
from objects import glob
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

    if not (t := await glob.players.get_user_offline(" ".join(args))):
        return "Player isn't online or couldn't be found in the database"

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

    if not (t := await glob.players.get_user_offline(" ".join(args))):
        return "Player isn't online or couldn't be found in the database"

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

    if not (t := await glob.players.get_user_offline(" ".join(args))):
        return "Player isn't online or couldn't be found in the database"

    if not t.is_restricted:
        return "Player isn't even restricted?"

    await glob.sql.execute("UPDATE users SET privileges = privileges + 4 WHERE id = %s", (t.id))

    return f"Successfully unrestricted {t.username}"

@register_command("bot")
async def bot_commands(p, chan, message):
    # usage: !bot <action>

    args = message.split(" ")[1:]

    if len(args) < 1:
        return f"{glob.bot.username.lower()}."

    if args[0] == "reconnect":
        if await glob.players.get_user(1):
            return f"{glob.bot.username} is already connected."

        await Louise.init()

        return f"Successfully connected {glob.bot.username}."

@register_command("roll")
async def roll(p, chan, message):
    # usage: !roll

    x = 100
    args = message.split(" ")

    if len(args) > 1:
        x = int(args[1])

    return f"{p.username} rolled {random.randint(0, x)} point(s)"

@register_command("stats")
async def user_stats(p, chan, message):
    # usage: !stats <username> <rx/vn>

    args = message.split(" ")[1:]

    if len(args) < 2:
        return "Usage: !stats <username> <rx/vn>"

    if not (t := await glob.players.get_user_offline(" ".join(args))):
        return "Player isn't online or couldn't be found in the database"

    relax = 0

    if args[1] == "rx":
        relax = 1

    ret = await t.get_stats(relax)

    return f"Stats for {t.username}:\n" \
           f"PP: {ret['pp']} (#{ret['rank']})\n" \
           f"Plays: {ret['playcount']} (lv{ret['level']})\n" \
           f"Accuracy: {ret['level']}%"