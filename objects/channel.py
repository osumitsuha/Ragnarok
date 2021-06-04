from objects.player import Player
from packets import writer
from objects import glob
from utils import log

class Channel:
    def __init__(self, name, description, public=True, 
                 admin=False, raw_name = None, ):
        self.name: str = name
        self.raw_name: str = raw_name if raw_name \
                                else name

        self.description: str = description
        self.players_len: int = 0
        self.public: bool = public
        self.admin: bool = admin

class Channels:
    def __init__(self):
        self.channels: list[Channel] = []

    async def add_channel(self, name, description, public, admin, raw_name=None):
        c = Channel(name, description, public, admin, raw_name)
        
        self.channels.append(c)

    def get_channel(self, name):
        for channel in self.channels:
            if channel.raw_name == name:
                return channel

    async def join_channel(self, p: Player, name):
        if not (chan := self.get_channel(name)):
            return # channel not found; ignore.

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
        if not channel.startswith("#"):
            u = await glob.players.get_user(channel) # channel is the users username in this instance

            u.enqueue(await writer.SendMessage(p.username, msg, channel))

        if not (chan := self.get_channel(channel)):
            return # channel not found; ignore.

        log.info(f"<{p.username}> {msg} [{channel}]")

        # TODO: checks.
        for u in glob.players.players:
            if p.id != u.id:
                u.enqueue(await writer.SendMessage(p.username, msg, channel))
