import aiohttp
from objects import glob
from utils import log
from constants.playmode import Mode
from constants.beatmap import Approved


class Beatmap:
    def __init__(self):
        """ A class made for handling osu! beatmaps.
        
        set_id: `int`
            The beatmaps set id

        map_id: `int`
            The beatmaps map id

        hash_md5: `str`
            The beatmaps hexadecimal.

        """
        self.set_id = 0
        self.map_id = 0
        self.hash_md5 = ""

        self.title = ""
        self.title_unicode = ""  # added
        self.version = ""
        self.artist = ""
        self.artist_unicode = ""  # added
        self.creator = ""
        self.creator_id = 0

        self.stars = 0.0
        self.od = 0.0
        self.ar = 0.0
        self.hp = 0.0
        self.cs = 0.0
        self.mode = 0
        self.bpm = 0.0
        self.max_combo = 0

        self.approved = Approved.PENDING

        self.submit_date = ""
        self.approved_date = ""
        self.latest_update = ""

        self.length_total = 0
        self.drain = 0

        self.plays = 0
        self.passes = 0
        self.favorites = 0

        self.rating = 0  # added

        self.scores: int = 0  # implementing in 300000 years

    @property
    def file(self):
        return f"{self.map_id}.osu"

    @property
    def pass_procent(self):
        return self.passes / self.plays * 100

    @property
    def full_title(self):
        return f"{self.artist} - {self.title} [{self.version}]"

    @property
    def display_title(self):
        return f"[bold:0,size:20]{self.artist_unicode}|{self.title_unicode}"  # You didn't see this

    @property
    def url(self):
        return f"https://mitsuha.pw/beatmapsets/{self.set_id}#{self.map_id}"

    @property
    def embed(self):
        return f"[{self.url} {self.full_title}]"

    @property
    def web_format(self):
        return f"{self.approved}|false|{self.map_id}|{self.set_id}|{self.scores}\n0\n{self.display_title}\n{self.rating}"

    @staticmethod
    def add_chart(name: str, prev=None, after=None) -> str:
        return f"{name}Before:{prev if prev else ''}|{name}After:{after}"

    @classmethod
    async def _get_beatmap_from_sql(cls, hash: str, beatmap_id: int):
        b = cls()

        ret = await glob.sql.fetch(
            "SELECT set_id, map_id, hash, title, title_unicode, "
            "version, artist, artist_unicode, creator, creator_id, stars, "
            "od, ar, hp, cs, mode, bpm, approved, submit_date, approved_date, "
            "latest_update, length, drain, plays, passes, favorites, rating "
            f"FROM beatmaps WHERE {'hash' if hash else 'map_id'} = %s",
            (hash or beatmap_id),
        )

        if not ret:
            return

        b.set_id = ret["set_id"]
        b.map_id = ret["map_id"]
        b.hash_md5 = ret["hash"]

        b.title = ret["title"]
        b.title_unicode = ret["title_unicode"]  # added
        b.version = ret["version"]
        b.artist = ret["artist"]
        b.artist_unicode = ret["artist_unicode"]  # added
        b.creator = ret["creator"]
        b.creator_id = ret["creator_id"]

        b.stars = ret["stars"]
        b.od = ret["od"]
        b.ar = ret["ar"]
        b.hp = ret["hp"]
        b.cs = ret["cs"]
        b.mode = ret["mode"]
        b.bpm = ret["bpm"]

        b.approved = ret["approved"]

        b.submit_date = ret["submit_date"]
        b.approved_date = ret["approved_date"]
        b.latest_update = ret["latest_update"]

        b.length_total = ret["length"]
        b.drain = ret["drain"]

        b.plays = ret["plays"]
        b.passes = ret["passes"]
        b.favorites = ret["favorites"]

        b.rating = ret["rating"]

        return b

    async def add_to_db(self):
        if await glob.sql.fetch(
            "SELECT 1 FROM beatmaps WHERE hash = %s LIMIT 1", (self.hash_md5)
        ):
            return  # ignore beatmaps there are already in db

        await glob.sql.execute(
            "INSERT INTO beatmaps (set_id, map_id, hash, title, title_unicode, "
            "version, artist, artist_unicode, creator, creator_id, stars, "
            "od, ar, hp, cs, mode, bpm, max_combo, approved, submit_date, approved_date, "
            "latest_update, length, drain, plays, passes, favorites, rating) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [*self.__dict__.values()][:-1],
        )

        log.info(f"Saved {self.full_title} ({self.hash_md5}) into database")

    @classmethod
    async def _get_beatmap_from_osuapi(cls, hash: str, beatmap_id):
        b = cls()

        async with aiohttp.ClientSession() as session:
            # get the beatmap with its hash
            async with session.get(
                "https://osu.ppy.sh/api/get_beatmaps?k=" + glob.osu_key + f"&{'h' if hash else 'b'}=" + hash or beatmap_id
            ) as resp:
                if not resp or resp.status != 200:
                    return

                if not (b_data := await resp.json()):
                    return

                ret = b_data[0]

        b.set_id = int(ret["beatmapset_id"])
        b.map_id = int(ret["beatmap_id"])
        b.hash_md5 = ret["file_md5"]

        b.title = ret["title"]
        b.title_unicode = ret["title_unicode"] or ret["title"]  # added
        b.version = ret["version"]
        b.artist = ret["artist"]
        b.artist_unicode = ret["artist_unicode"] or ret["artist"]  # added
        b.creator = ret["creator"]
        b.creator_id = int(ret["creator_id"])

        b.stars = float(ret["difficultyrating"])
        b.od = float(ret["diff_overall"])
        b.ar = float(ret["diff_approach"])
        b.hp = float(ret["diff_drain"])
        b.cs = float(ret["diff_size"])
        b.mode = Mode(int(ret["mode"])).value
        b.bpm = float(ret["bpm"])
        b.max_combo = (
            0 if ret["max_combo"] is None else int(ret["max_combo"])
        )  # fix taiko and mania "null" combo

        b.approved = Approved(int(ret["approved"])).value

        b.submit_date = ret["submit_date"]

        if ret["approved_date"]:
            b.approved_date = ret["approved_date"]
        else:
            b.approved_date = "0"

        b.latest_update = ret["last_update"]

        b.length_total = int(ret["total_length"])
        b.drain = int(ret["hit_length"])

        b.plays = 0
        b.passes = 0
        b.favorites = 0

        b.rating = float(ret["rating"])

        await b.add_to_db()

        return b

    @classmethod
    async def get_beatmap(cls, hash: str = "", beatmap_id=0):
        self = cls()  # trollface

        if not (ret := await self._get_beatmap_from_sql(hash, beatmap_id)):
            if not (ret := await self._get_beatmap_from_osuapi(hash, beatmap_id)):
                return

        return ret
