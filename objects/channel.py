from objects.player import Player
from packets import writer
import time
from objects import glob
from utils import log

class Channel:
    def __init__(self, name, description, public=True, 
                 staff=False, raw_name = None, ):
        self.name: str = name
        self.raw_name: str = raw_name if raw_name \
                                else name

        self.description: str = description
        self.players_len: int = 0
        self.public: bool = public
        self.staff: bool = staff

class Channels:
    def __init__(self):
        self.channels: list[Channel] = []

    async def add_channel(self, name, description, public, staff, raw_name=None):
        c = Channel(name, description, public, staff, raw_name)
        
        self.channels.append(c)

    def get_channel(self, name):
        for channel in self.channels:
            if channel.raw_name == name:
                return channel

    async def join_channel(self, p: Player, name):
        if not (chan := self.get_channel(name)):
            return # channel not found; ignore.

        if not p.is_staff and chan.staff:
            return # ignore if user isn't staff on staff chat

        p.enqueue(await writer.ChanJoinSuccess(name))

        p.channels.append(chan)
        chan.players_len += 1

        glob.players.enqueue(await writer.ChanInfo(name))


    async def leave_channel(self, p: Player, name, kicked = False):
        if not (chan := self.get_channel(name)):
            return # channel not found; ignore.

        p.channels.remove(chan)
        chan.players_len -= 1

        if kicked:
            p.enqueue(await writer.ChanKick(name))
        
        glob.players.enqueue(await writer.ChanInfo(name))

    async def message(self, p, msg, channel):
        if not (self.get_channel(channel) and channel.startswith("#")):
            return # channel not found; ignore.

        if p.is_restricted:
            return # ignore if the user is restricted

        if not channel.startswith("#"):
            u = await glob.players.get_user(channel) # channel is the users username in this instance

            u.enqueue(await writer.SendMessage(p.username, msg, channel))


        # TODO: checks.
        for u in glob.players.players:
            if p.id != u.id:
                u.enqueue(await writer.SendMessage(p.username, msg, channel))

        log.info(f"<{p.username}> {msg} [{channel}]")

        if msg.startswith(glob.prefix):
            parsed = msg.split(" ")[0][1:]
            
            for cmd in glob.registered_commands:
                if parsed == cmd["cmd"]:
                    if p.id == 1:
                        return # ignore bot
                        
                    if not p.privileges & cmd["required_perms"]:
                        return # don't say anything if no perms

                    resp = await cmd["trigger"](p, channel, msg)

                    glob.players.enqueue(await writer.SendMessage("Louise", resp, channel))
        

