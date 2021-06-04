from enum import IntEnum
import aiohttp
from objects import glob
from utils import log

class Approved(IntEnum):
    GRAVEYARD = -2
    WIP = -1
    PENDING = 0

    RANKED = 1
    APPROVED = 2
    QUALIFIED = 3
    LOVED = 4

class Beatmap:
    def __init__(self, hash: str, set_id: int = 0, map_id: int = 0):
        self.set_id = set_id
        self.map_id = map_id
        self.hash_md5 = hash

        self.title = ""
        self.title_unicode = "" # added
        self.version = ""
        self.artist = ""
        self.artist_unicode = "" # added
        self.creator = ""
        self.creator_id = 0

        self.stars = 0.0
        self.od = 0.0
        self.ar = 0.0
        self.hp = 0.0
        self.cs = 0.0
        self.mode = 0
        self.bpm = 0.0

        self.approved = Approved.PENDING

        self.submit_date = ""
        self.approved_date = ""
        self.latest_update = ""

        self.length_total = 0
        self.drain = 0

        self.plays = 0
        self.passes = 0
        self.favorites = 0

        self.rating = 0 # added

        self.scores = [] # implementing in 300000 years 

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
        return f"[bold:0,size:20]{self.artist_unicode}|{self.title_unicode}" # You didn't see this

    @property
    def url(self):
        return f"https://mitsuha.pw/beatmapsets/{self.set_id}#{self.map_id}"

    @property
    def embed(self):
        return f"[{self.url} {self.full_title}]"

    @property
    def web_format(self):
        return f"{self.approved}|true|{self.map_id}|{self.set_id}|{len(self.scores)}\n0\n{self.display_title}\n{self.rating}"

    async def _get_beatmap_from_sql(self):
        ret = await glob.sql.fetch(
            "SELECT map_id, set_id, hash, title, title_unicode, version, "
            "artist, artist_unicode, creator, creator_id, stars, "
            "od, ar, hp, cs, mode, bpm, count_circles, "
            "count_spinners, count_sliders, approved, "
            "submit_date, approved_date, latest_update, "
            "length, drain, plays, passes, faovrites, rating FROM beatmaps "
            "WHERE hash = %s LIMIT 1", (self.hash_md5)
        )

        if not ret:
            return False

        if not self.set_id:
            self.set_id = ret["set_id"]

        if not self.map_id:
            self.map_id = ret["map_id"]

        self.title = ret["title"]
        self.title_unicode = ret["title_unicode"] #added
        self.version = ret["version"]
        self.artist = ret["artist"]
        self.artist_unicode = ret["artist_unicode"] #added
        self.creator = ret["creator"]
        self.creator_id = ret["creator_id"]
        
        self.stars = ret["stars"]
        self.od = ret["od"]
        self.ar = ret["ar"]
        self.hp = ret["hp"]
        self.cs = ret["cs"]
        self.mode = ret["mode"]
        self.bpm = ret["bpm"]

        self.approved = Approved(ret["approved"])

        self.submit_date = ret["submit_date"]
        self.approved_date = ret["approved_date"]
        self.latest_update = ret["latest_update"]
       
        self.length_total = ret["length"]
        self.drain = ret["drain"]

        self.plays = ret["plays"]
        self.passes = ret["passes"]
        self.favorites = ret["favorites"]

        self.rating = ret["rating"]

        return True

    async def _get_beatmap_from_osuapi(self):
        async with aiohttp.ClientSession() as session:
            # TODO: add more ways to find beatmap, by it's set ID
            async with session.get("https://osu.ppy.sh/api/get_beatmaps?k="+glob.osu_key+"&h="+self.hash_md5) as resp:
                if not resp or resp.status != 200:
                    return False

                if not (b_data := await resp.json()):
                    return False

                ret = b_data[0]

        if not self.set_id:
            self.set_id = int(ret["beatmapset_id"])

        if not self.map_id:
            self.map_id = int(ret["beatmap_id"])

        self.title = ret["title"]
        self.title_unicode = ret["title_unicode"] # added
        self.version = ret["version"]
        self.artist = ret["artist"]
        self.artist_unicode = ret["artist_unicode"] # added
        self.creator = ret["creator"]
        self.creator_id = int(ret["creator_id"])
        
        self.stars = float(ret["difficultyrating"])
        self.od = float(ret["diff_overall"])
        self.ar = float(ret["diff_approach"])
        self.hp = float(ret["diff_drain"])
        self.cs = float(ret["diff_size"])
        self.mode = int(ret["mode"])
        self.bpm = float(ret["bpm"])

        self.approved = Approved(int(ret["approved"]))

        self.submit_date = ret["submit_date"]
        self.approved_date = ret["approved_date"]
        self.latest_update = ret["last_update"]
       
        self.length_total = int(ret["total_length"])
        self.drain = int(ret["hit_length"])

        self.plays = 0
        self.passes = 0
        self.favorites = 0

        self.rating = float(ret["rating"])

        return True

    async def get_beatmap(self):
        #if not (ret := await self._get_beatmap_from_sql()): gonna implement later...
        if not (ret := await self._get_beatmap_from_osuapi()):
            return

        return ret

    
