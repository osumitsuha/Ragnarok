from py3rijndael.rijndael import RijndaelCbc
from py3rijndael.paddings import ZeroPadding
from constants.beatmap import Approved
from objects.beatmap import Beatmap
from constants.playmode import Mode
from constants.playmode import Mode
from dataclasses import dataclass
from objects.player import Player
from constants.mods import Mods
from base64 import b64decode
from enum import IntEnum
from objects import glob
from utils import score
import oppai as pp
import math
import time


@dataclass
class ScoreFrame:
    time: int = 0
    id: int = 0

    count_300: int = 0
    count_100: int = 0
    count_50: int = 0

    count_geki: int = 0
    count_katu: int = 0
    count_miss: int = 0

    score: int = 0
    max_combo: int = 0
    combo: int = 0

    perfect: bool = False

    current_hp: int = 0
    tag_byte: int = 0

    score_v2: bool = False


class SubmitStatus(IntEnum):
    FAILED = 0
    QUIT = 1
    PASSED = 2
    BEST = 3


class Score:
    def __init__(self):
        self.player: Player = None
        self.map: Beatmap = None

        self.id: int = 0

        self.score: int = 0
        self.pp: float = 0.0

        self.count_300: int = 0
        self.count_100: int = 0
        self.count_50: int = 0

        self.count_geki: int = 0
        self.count_katu: int = 0
        self.count_miss: int = 0

        self.max_combo: int = 0
        self.accuracy: float = 0.0

        self.perfect: bool = False

        self.rank: str = ""

        self.mods: int = 0
        self.status: SubmitStatus = SubmitStatus.FAILED

        self.play_time: int = 0

        self.mode: Mode = Mode.OSU

        self.submitted: int = math.ceil(time.time())

        self.relax: bool = False

        self.position: int = 0

        # previous_best
        self.pb: "Score" = None

    @property
    def web_format(self) -> str:
        return (
            f"\n{self.id}|{self.player.username}|{self.score if not self.relax else math.ceil(self.pp)}|"
            f"{self.max_combo}|{self.count_50}|{self.count_100}|{self.count_300}|{self.count_miss}|"
            f"{self.count_katu}|{self.count_geki}|{self.perfect}|{self.mods}|{self.player.id}|"
            f"{self.position}|{self.submitted}|1"
        )

    @classmethod
    async def set_data_from_sql(cls, score_id: int) -> "Score":
        data = await glob.sql.fetch(
            "SELECT id, user_id, hash_md5, score, pp, count_300, count_100, "
            "count_50, count_geki, count_katu, count_miss, "
            "max_combo, accuracy, perfect, rank, mods, status, "
            "play_time, mode, submitted, relax FROM scores "
            "WHERE id = %s",
            (score_id),
        )

        s = cls()

        s.player = await glob.players.get_user_offline(data["user_id"])
        s.map = await Beatmap.get_beatmap(data["hash_md5"])

        s.score = data["score"]
        s.pp = data["pp"]

        s.count_300 = data["count_300"]
        s.count_100 = data["count_100"]
        s.count_50 = data["count_50"]
        s.count_geki = data["count_geki"]
        s.count_katu = data["count_katu"]
        s.count_miss = data["count_miss"]

        s.max_combo = data["max_combo"]
        s.accuracy = data["accuracy"]

        s.perfect = data["perfect"]

        s.rank = data["rank"]
        s.mods = data["mods"]

        s.play_time = data["play_time"]

        s.status = SubmitStatus(data["status"])
        s.mode = Mode(data["mode"])

        s.submitted = data["submitted"]

        s.relax = data["relax"]

        await s.calculate_position()

        return s

    @classmethod
    async def set_data_from_submission(
        cls, score_enc: bytes, iv: bytes, key: str, exited: int
    ) -> "Score":
        score_latin = b64decode(score_enc).decode("latin_1")
        iv_latin = b64decode(iv).decode("latin_1")

        data = (
            RijndaelCbc(key, iv_latin, ZeroPadding(32), 32)
            .decrypt(score_latin)
            .decode()
            .split(":")
        )

        s = cls()

        s.player = glob.players.get_user(data[1].rstrip())

        if not s.player:
            return

        if data[0] in glob.beatmaps:
            s.map = glob.beatmaps[data[0]]
        else:
            s.map = await Beatmap.get_beatmap(data[0])

        (
            s.count_300,
            s.count_100,
            s.count_50,
            s.count_geki,
            s.count_katu,
            s.count_miss,
            s.score,
            s.max_combo,
        ) = map(int, data[3:-7])

        s.mode = Mode(int(data[15]))

        s.accuracy = score.calculate_accuracy(
            s.mode,
            s.count_300,
            s.count_100,
            s.count_50,
            s.count_geki,
            s.count_katu,
            s.count_miss,
        )

        s.perfect = s.max_combo == s.map.max_combo

        s.rank = data[12]

        s.mods = int(data[13])
        passed = data[14] == "True"

        if exited:
            s.status = SubmitStatus.QUIT

        s.relax = bool(int(data[13]) & Mods.RELAX)

        if passed:
            await s.calculate_position()

            if Approved(s.map.approved - 1) not in (
                Approved.LOVED,
                Approved.PENDING,
                Approved.WIP,
                Approved.GRAVEYARD,
            ):
                ez = pp.ezpp_new()

                if s.mods:
                    pp.ezpp_set_mods(ez, s.mods)

                pp.ezpp_set_combo(ez, s.max_combo)
                pp.ezpp_set_nmiss(ez, s.count_miss)
                pp.ezpp_set_accuracy_percent(ez, s.accuracy)

                pp.ezpp(ez, f".data/beatmaps/{s.map.file}")
                s.pp = pp.ezpp_pp(ez)

                pp.ezpp_free(ez)

            # find our previous best score on the map
            if prev_best := await glob.sql.fetch(
                "SELECT id FROM scores WHERE user_id = %s "
                "AND relax = %s AND hash_md5 = %s "
                "AND mode = %s AND status = 3 LIMIT 1",
                (s.player.id, s.relax, s.map.hash_md5, s.mode.value),
            ):
                s.pb = await Score.set_data_from_sql(prev_best["id"])

                # if we found a personal best score
                # that has more score on the map,
                # we set it to passed.
                if s.pb.pp < s.pp if s.relax else s.pb.score < s.score:
                    s.status = SubmitStatus.BEST
                    s.pb.status = SubmitStatus.PASSED

                    await glob.sql.execute(
                        "UPDATE scores SET status = 2 WHERE user_id = %s AND relax = %s "
                        "AND hash_md5 = %s AND mode = %s AND status = 3",
                        (s.player.id, s.relax, s.map.hash_md5, s.mode.value),
                    )
                else:
                    s.status = SubmitStatus.PASSED
            else:
                # if we find no old personal best
                # we can just set the status to best
                s.status = SubmitStatus.BEST
        else:
            s.status = SubmitStatus.FAILED

        # Currently all I need for this checksum
        # to work, is a storyboard checksum? Yeah,
        # I don't know either. I KNOW, nvm.

        # security_hash = RijndaelCbc(key, iv_latin, ZeroPadding(32), 32).decrypt(b64decode(security_hash).decode("latin_1")).decode()
        # reci_check_sum = data[2]

        # check_sum = md5(
        #     f"chickenmcnuggets"
        #     f"{s.count_100 + s.count_300}o15{s.count_50}{s.count_geki}"
        #     f"smustard{s.count_katu}{s.count_miss}uu"
        #     f"{s.map.hash_md5}{s.max_combo}{str(s.perfect)}"
        #     f"{s.player.username}{s.score}{s.rank}{s.mods}Q{str(s.passed)}"
        #     f"{s.mode}{data[17].strip()}{data[16]}{security_hash}{storyboardchecksum}"
        #     .encode()
        # ).hexdigest()

        # if reci_check_sum != check_sum:
        #     log.error(f"{s.player.username} tried to submit a score with an invalid score checksum.")
        #     return

        return s

    async def calculate_position(self) -> None:
        ret = await glob.sql.fetch(
            "SELECT COUNT(*) AS rank FROM scores s "
            "INNER JOIN beatmaps b ON b.hash = s.hash_md5 "
            "INNER JOIN users u ON u.id = s.user_id "
            "WHERE s.score > %s AND s.relax = %s "
            "AND b.hash = %s AND u.privileges & 4 "
            "AND s.status = 3 AND s.mode = %s "
            "ORDER BY s.score DESC, s.submitted DESC",
            (self.score, self.relax, self.map.hash_md5, self.mode.value),
        )

        self.position = ret["rank"] + 1

    async def save_to_db(self) -> None:
        await glob.sql.execute(
            "INSERT INTO scores (hash_md5, user_id, score, pp, "
            "count_300, count_100, count_50, count_geki, "
            "count_katu, count_miss, max_combo, accuracy, "
            "perfect, rank, mods, status, play_time, "
            " mode, submitted, relax) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s)",
            (
                self.map.hash_md5,
                self.player.id,
                self.score,
                self.pp,
                self.count_300,
                self.count_100,
                self.count_50,
                self.count_geki,
                self.count_katu,
                self.count_miss,
                self.max_combo,
                self.accuracy,
                self.perfect,
                self.rank,
                self.mods,
                self.status.value,
                self.play_time,
                self.mode.value,
                self.submitted,
                self.relax,
            ),
        )
