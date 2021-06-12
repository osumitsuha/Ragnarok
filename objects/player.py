from constants.status import bStatus
from constants.privileges import Privileges
from constants.presence import PresenceFilter
from constants.mods import Mods
from constants.playmode import Mode
from objects.match import Match
from utils import log
from objects import glob
from packets import writer
import time
import uuid

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
        self.current_mods: Mods = Mods.NONE
        self.play_mode: int = Mode.OSU
        self.beatmap_id: int = -1

        self.friends: set[int] = set()
        self.channels: list = []
        self.spectators: list[Player] = []
        self.spectating: Player = None
        self.match: Match = None

        # Never played
        self.ranked_score: int = 0
        self.accuracy: float = 0.0
        self.playcount: int = 0
        self.total_score: int = 0
        self.level: float = 0.0
        self.rank: int = 0
        self.pp: int = 0

        self.relax: int = 0 # 0 for vn / 1 for rx

        self.block_unknown_pms = kwargs.get("block_nonfriend", 0)

        self.queue = bytearray()

        self.login_time = time.time()

        self.bot = False

        self.is_restricted = not (self.privileges & Privileges.VERIFIED)
        self.is_staff = self.privileges & Privileges.BAT
    
    @property
    def embed(self) -> str:
        return f"[https://osu.mitsuha.pw/users/{self.id} {self.username}]"
    
    @property
    def url(self) -> str:
        return f"https://osu.mitsuha.pw/users/{self.id}"

    def safe_username(self, name) -> str:
        return name.lower().replace(" ", "_")

    @staticmethod
    def generate_token() -> str:
        return uuid.uuid4().hex

    def enqueue(self, packet: bytes) -> None:
        self.queue += packet

    def dequeue(self) -> None:
        if self.queue:
            ret = bytes(self.queue) 
            self.queue.clear()
            return ret

        return b""

    async def get_stats(self, relax: int = 0) -> dict:
        # TODO: Make other modes avaliable

        table = ("stats", "stats_rx")[relax]

        ret = await glob.sql.fetch(
            "SELECT ranked_score_std AS ranked_score, "
            "total_score_std AS total_score, accuracy_std AS accuracy, "
            "playcount_std AS playcount, pp_std AS pp, "
            f"level_std AS level FROM {table} " 
            "WHERE id = %s", (self.id)
        )

        if ret["pp"] >= 1:
            # if the users pp is 
            # higher or equal to
            # one, add rank to the user
            rank = await glob.sql.fetch(
                f"SELECT COUNT(*) AS rank FROM {table} t "
                "INNER JOIN users u ON u.id = t.id "
                "WHERE t.id != %s AND t.pp_std > %s "
                "ORDER BY t.pp_std DESC, t.total_score_std DESC LIMIT 1",
                (self.id, self.pp)
            )

            ret["rank"] = rank["rank"]+1
        else:
            # if not, make the user
            # not display any rank. (0)
            ret["rank"] = 0

        return ret

    # might do this differently at some point?
    async def update_stats(self) -> bool:
        ret = await self.get_stats(self.relax)

        self.ranked_score = ret["ranked_score"]
        self.accuracy = ret["accuracy"]
        self.playcount = ret["playcount"]
        self.total_score = ret["total_score"]
        self.level = ret["level"]
        self.rank = ret["rank"]
        self.pp = int(ret["pp"])

        return True

    async def logout(self) -> None:
        if self.channels: 
            for channel in self.channels[:]:
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

    async def add_spectator(self, p) -> None:
        # TODO: Create temp spec channel
        joined = await writer.FellasJoinSpec(p.id)

        for s in self.spectators:
            s.enqueue(joined)
            p.enqueue(await writer.FellasJoinSpec(s.id))

        self.enqueue(await writer.UsrJoinSpec(p.id))
        self.spectators.append(p)

        p.spectating = self

    async def remove_spectator(self, p) -> None:
        # TODO: Remove chan and part chan
        left = await writer.FellasLeftSpec(p.id)

        for s in self.spectators:
            s.enqueue(left)

        self.enqueue(await writer.UsrLeftSpec(p.id))
        self.spectators.remove(p)

        p.spectating = None

    async def get_friends(self) -> None:
        friends = await glob.sql.fetchall("SELECT user_id2 FROM friends WHERE user_id1 = %s", (self.id))
        for player in friends:
            self.friends.add(player[0])

    async def handle_friend(self, user: int) -> None:
        if not (t := await glob.players.get_user(user)):
            return # user isn't online; ignore

        # remove friend
        if await glob.sql.fetch("SELECT 1 FROM friends WHERE user_id1 = %s AND user_id2 = %s", (self.id, user)):
            await glob.sql.execute("DELETE FROM friends WHERE user_id1 = %s AND user_id2 = %s", (self.id, user))
            self.friends.remove(user)
            
            log.info(f"{self.username} removed {t.username} as friends.")
            return

        # add friend
        await glob.sql.execute("INSERT INTO friends (user_id1, user_id2) VALUES (%s, %s)", (self.id, user))
        self.friends.add(user)

        log.info(f"{self.username} added {t.username} as friends.")

    async def restrict(self) -> None:
        if self.is_restricted:
            return # just ignore if the user
                   # is already restricted.

        self.privileges -= Privileges.VERIFIED

        await glob.db.execute("UPDATE users SET privileges -= 4 WHERE id = %s", (self.id))

        # notify user
        self.enqueue(await writer.Notification("Your account has been put in restricted mode!"))

        log.info(f"{self.username} has been put in restricted mode!")
