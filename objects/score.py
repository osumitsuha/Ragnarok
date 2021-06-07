from py3rijndael.rijndael import RijndaelCbc
from py3rijndael.paddings import ZeroPadding
from constants.playmode import Mode
from objects.player import Player
from objects.beatmap import Beatmap
from constants.mods import Mods
from base64 import b64decode
from objects import glob
from utils import log
import math
import time

class Score:
    def __init__(self, p: Player = None, **kwargs):
        self.user_id = kwargs.get("user_id", 1)
        
        self.player: Player = p
        self.map: Beatmap = kwargs.get("map", None)

        self.id: int = kwargs.get("id", 0)

        self.score: int = kwargs.get("score", 0)
        self.pp: float = kwargs.get("pp", 0.0)

        self.count_300: int = kwargs.get("count_300", 0)
        self.count_100: int = kwargs.get("count_100", 0)
        self.count_50: int = kwargs.get("count_50", 0)

        self.count_geki: int = kwargs.get("count_geki", 0)
        self.count_katu: int = kwargs.get("count_katu", 0)
        self.count_miss: int = kwargs.get("count_miss", 0)

        
        self.max_combo: int = kwargs.get("max_combo", 0)
        self.accuracy: float = kwargs.get("accuracy", 0.0)
        
        self.perfect: bool = kwargs.get("perfect", False)

        self.rank: str = kwargs.get("rank", "")

        self.mods: int = kwargs.get("mods", 0)
        self.passed: bool = kwargs.get("passed", False)
        self.exited: bool = kwargs.get("exited", False)

        self.play_time: int = kwargs.get("play_time", 0)

        self.mode: int = kwargs.get("mode", 0)
        
        self.submitted: int = kwargs.get("submitted", math.ceil(time.time()))

        self.relax: bool = kwargs.get("relax", False)

        self.position: int = 0

    @property
    def web_format(self):
        return f"\n{self.id}|{self.player.username}|{self.score if not self.relax else math.ceil(self.pp)}|" \
               f"{self.max_combo}|{self.count_50}|{self.count_100}|{self.count_300}|{self.count_miss}|" \
               f"{self.count_katu}|{self.count_geki}|{self.perfect}|{self.mods}|{self.player.id}|" \
               f"{self.position}|{self.submitted}|1"

    @classmethod
    async def set_data_from_submission(cls, 
            score_enc: bytes, iv: bytes, 
            key: str, exited: int, ft: int
        ) -> None:
        score_latin = b64decode(score_enc).decode("latin_1")
        iv_latin = b64decode(iv).decode("latin_1")

        data = RijndaelCbc(key, iv_latin, ZeroPadding(32), 32).decrypt(score_latin).decode().split(":")

        s = cls()

        s.player = await glob.players.get_user(data[1].rstrip())

        if data[0] in glob.beatmaps:
            s.map = glob.beatmaps[data[0]]
        else:
            s.map = await Beatmap.get_beatmap(data[0])
        
        (s.count_300, s.count_100, s.count_50, s.count_geki, s.count_katu, s.count_miss, s.score, s.max_combo) = map(int, data[3:-7])

        s.mode = int(data[15])

        s.calculate_accuracy()
        s.perfect = s.accuracy == 100.0

        s.rank = data[12]

        s.mods = int(data[13])
        s.passed = data[14] == "True"
        s.exited = exited == 1

        s.play_time = ft or s.map.drain * 1000

        if s.mods & Mods.DOUBLETIME or s.mods & Mods.NIGHTCORE:
            s.play_time = ft or s.map.drain * (1 - .33) * 1000

        if s.mods & Mods.HALFTIME:
            s.play_time = ft or s.map.drain * 1.33 * 1000

        s.relax = bool(int(data[13]) & Mods.RELAX)

        await s.calculate_position() 

        return s

    async def calculate_position(self):
        ret = await glob.sql.fetch(
            "SELECT COUNT(*) AS rank FROM scores s "
            "INNER JOIN beatmaps b ON b.hash = s.hash_md5 "
            "INNER JOIN users u ON u.id = s.user_id "
            "WHERE s.score > %s AND s.relax = %s "
            "AND b.hash = %s AND u.privileges & 4 "
            "AND s.passed = 1 AND s.mode = %s "
            "ORDER BY s.score DESC, s.submitted DESC",
            (self.score, self.relax, 
             self.map.hash_md5, self.mode, )
        )

        self.position = ret["rank"] + 1

    def calculate_accuracy(self):
        if self.mode == Mode.OSU:
            if glob.debug:
                log.debug("Calculating accuracy for standard")
            
            acc = (50 * self.count_50 + 100 * self.count_100 + 300 * self.count_300) / (300 * (self.count_miss + self.count_50 + self.count_100 + self.count_300))

        if self.mode == Mode.TAIKO:
            if glob.debug:
                log.debug("Calculating accuracy for taiko")
            
            acc = (0.5*self.count_100 + self.count_300) / (self.count_miss + self.count_100 + self.count_300)

        if self.mode == Mode.CATCH:
            if glob.debug:
                log.debug("Calculating accuracy for catch the beat")

            acc = (self.count_50 + self.count_100 + self.count_300) / (self.count_katu + self.count_miss + self.count_50 + self.count_100 + self.count_300)

        if self.mode == Mode.MANIA:
            if glob.debug:
                log.debug("Calculating accuracy for mania")

            log.debug(self.__dict__)

            acc = (50 * self.count_50 + 100 * self.count_100 + 200 * self.count_katu + 300 * (self.count_300 + self.count_geki)) / (300 * (self.count_miss + self.count_50 + self.count_100 + self.count_katu + self.count_300 + self.count_geki))

        self.accuracy = acc * 100

    async def save_to_db(self):
        # get old personal best,
        # if there is one.
        if (ret := await glob.sql.fetch(
            "SELECT score, mode, relax, count_300, "
            "count_100, count_50, count_geki, count_katu, "
            "count_miss, max_combo, accuracy, perfect, "
            "perfect, rank, mods, passed, exited, play_time, "
            "mode, submitted, pp, id, user_id FROM scores "
            "WHERE user_id = %s AND relax = %s AND hash_md5 = %s "
            "AND mode = %s AND passed = 1 LIMIT 1", 
            (self.player.id, self.relax, self.map.hash_md5, self.mode))
        ):
            pb = Score(**ret)

            pb.player = await glob.players.get_user_by_id(ret["user_id"])
            pb.map = self.map

            await pb.calculate_position()

            # if we found a passed score
            # that has more score on the map, 
            # we set it to not passed.
            if pb.score < self.score:
                await glob.sql.execute(
                    "UPDATE scores SET passed = 0 WHERE user_id = %s AND relax = %s "
                    "AND hash_md5 = %s AND mode = %s  AND passed = 1", 
                    (self.player.id, self.relax, self.map.hash_md5, self.mode)
                )

            if [pb.web_format, pb.mode, pb.relax] in self.map.scores:
                if glob.debug:
                    log.debug("Removing a players old personal best from cache.")

                self.map.scores.remove([pb.web_format, pb.mode, pb.relax])

        await glob.sql.execute(
            "INSERT INTO scores (hash_md5, user_id, score, pp, "
            "count_300, count_100, count_50, count_geki, "
            "count_katu, count_miss, max_combo, accuracy, "
            "perfect, rank, mods, passed, exited, "
            "play_time, mode, submitted, relax) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                self.map.hash_md5, self.player.id, self.score, self.pp,
                self.count_300, self.count_100, self.count_50, self.count_geki, 
                self.count_katu, self.count_miss, self.max_combo, self.accuracy,
                self.perfect, self.rank, self.mods, self.passed, self.exited,
                self.play_time, self.mode, self.submitted, self.relax
            )
        )