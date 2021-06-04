from constants.status import bStatus
from constants.privileges import Privileges
from constants.presence import PresenceFilter
from utils import log
from objects import glob
from enum import unique, IntEnum
from packets import writer
import time
import uuid

@unique
class GameMode(IntEnum):
    OSU = 0
    TAIKO = 1
    FRUITS = 2
    MANIA = 3

class Player:
    def __init__(self, username: str, id: int, privileges: int, 
                 passhash: str, ip: str, **kwargs) -> None:
        self.id = id
        self.username = username
        self.safe_name = self.safe_username(self.username)
        self.privileges = privileges
        self.passhash = passhash
        self.country = 21

        self.ip = ip,
        self.longitude = 0.0
        self.latitude = 0.0
        self.timezone = 26
        self.client_version = kwargs.get("version", 0.0),
        
        if kwargs.get("token"):
            self.token = kwargs.get("token")
        else:
            self.token = self.generate_token()

        self.presence_filter = PresenceFilter.NIL

        self.status = bStatus.IDLE
        self.status_text: str = "on Vanilla"
        self.beatmap_md5: str = ""
        self.current_mods = 0
        self.play_mode: int = GameMode.OSU
        self.beatmap_id: int = 12

        self.friends: set[int] = set()
        self.channels: list = []
        self.spectators: list[Player] = []
        self.spectating: Player = None
        self.match = None

        # Never played
        self.ranked_score: int = 0
        self.accuracy: float = 0.0
        self.playcount: int = 0
        self.total_score: int = 0
        self.rank: int = 0
        self.pp: int = 0

        self.block_unknown_pms = kwargs.get("block_nonfriend", 0)

        self.queue = bytearray()

        self.login_time = time.time()

        self.bot = False

        self.is_restricted = not (self.privileges & Privileges.VERIFIED)
        self.is_staff = self.privileges & Privileges.BAT

    def safe_username(self, name) -> str:
        return name.lower().replace(" ", "_")

    @staticmethod
    def generate_token():
        return uuid.uuid4().hex

    def enqueue(self, packet: bytes):
        self.queue += packet

    def dequeue(self):
        if self.queue:
            ret = bytes(self.queue) 
            self.queue.clear()
            return ret

        return b""

    async def logout(self):
        if self.channels: 
            for channel in self.channels:
                await glob.channels.leave_channel(self, channel.raw_name, kicked=True)

            self.channels.clear()
            
        if self.match:
            # proper match parting code...
            ...

        if self.spectating: 
            # leave spectating code and stuff idk
            ...

        await glob.players.remove_user(self)

        for player in glob.players.players:
            player.enqueue(await writer.Logout(self.id))

    async def add_spectator(self, p):
        # TODO: Create temp spec channel
        joined = await writer.FellasJoinSpec(p.id)
        for s in self.spectators:
            s.enqueue(joined)
            p.enqueue(await writer.FellasJoinSpec(s.id))

        self.enqueue(await writer.UsrJoinSpec(p.id))
        self.spectators.append(p)
        p.spectating = self

    async def remove_spectator(self, p):
        # TODO: Remove chan and part chan
        left = await writer.FellasLeftSpec(p.id)
        for s in self.spectators:
            s.enqueue(left)
        self.enqueue(await writer.UsrLeftSpec(p.id))
        self.spectators.remove(p)
        p.spectating = None

    async def get_friends(self):
        friends = await glob.sql.fetchall("SELECT user_id2 FROM friends WHERE user_id1 = %s", (self.id))
        for player in friends:
            self.friends.add(player[0])
        else:
            self.friends.add(1)

    async def handle_friend(self, user: int):
        # remove friend
        if await glob.sql.fetch("SELECT 1 FROM friends WHERE user_id1 = %s AND user_id2 = %s", (self.id, user)):
            await glob.sql.execute("DELETE FROM friends WHERE user_id1 = %s AND user_id2 = %s", (self.id, user))
            self.friends.remove(user)
            log.info(f"{self.username} removed {user} as friends.")
            return

        # add friend
        await glob.sql.execute("INSERT INTO friends (user_id1, user_id2) VALUES (%s, %s)", (self.id, user))
        self.friends.add(user)

        log.info(f"{self.username} added {user} as friends.")
