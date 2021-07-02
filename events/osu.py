from objects.beatmap import Beatmap
from objects.channel import Channel
from constants.mods import Mods
from objects import glob
from utils import log
from objects.score import Score, SubmitStatus
from collections import defaultdict
from constants.player import Privileges
from lenhttp import Router, Request
from typing import Callable
from functools import wraps
from anticheat import run
import numpy as np
import aiofiles
import aiohttp
import math
import os
import copy
import bcrypt
import hashlib
import asyncio


def check_auth(u: str, pw: str, method="GET"):
    def decorator(cb: Callable) -> Callable:
        @wraps(cb)
        async def wrapper(req, *args, **kwargs):
            if method == "GET":
                player = req.get_args[u]
                password = req.get_args[pw]
            else:
                player = req.post_args[u]
                password = req.post_args[pw]

            if not (p := glob.players.get_user(player)):
                return b""

            if p.passhash in glob.bcrypt_cache:
                if password.encode("utf-8") != glob.bcrypt_cache[p.passhash]:
                    return b""

            return await cb(req, *args, **kwargs)

        return wrapper

    return decorator

glob.osu = Router({f"osu.{glob.domain}", f"127.0.0.1:{glob.port}"})

@glob.osu.add_endpoint("/users", methods=["POST"])
async def registration(req: Request):
    uname = req.post_args["user[username]"]
    email = req.post_args["user[user_email]"]
    pwd = req.post_args["user[password]"]

    error_response = defaultdict(list)

    if await glob.sql.fetch("SELECT 1 FROM users WHERE username = %s", [uname]):
        error_response["username"].append("A user with that name already exists in our database.")

    if await glob.sql.fetch("SELECT 1 FROM users WHERE email = %s", [email]):
        error_response["user_email"].append("A user with that name already exists in our database.")

    if error_response:
        return req.return_json(200, {"form_error": {"user": error_response}})

    if req.post_args["check"] == "0":
        pw_md5 = hashlib.md5(pwd.encode()).hexdigest().encode()
        pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())

        id = await glob.sql.execute(
            "INSERT INTO users (id, username, safe_username, passhash, "
            "email, privileges, latest_activity_time, registered_time) "
            "VALUES (NULL, %s, %s, %s, %s, %s, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())",
            [uname, uname.lower().replace(" ", "_"), pw_bcrypt, email, Privileges.PENDING.value]
        )

        await glob.sql.execute("INSERT INTO stats (id) VALUES (%s)", [id])
        await glob.sql.execute("INSERT INTO stats_rx (id) VALUES (%s)", [id])

    return b"ok"


async def get_beatmap_file(id: int):
    if not os.path.exists(f".data/beatmaps/{id}.osu"):
        async with aiohttp.ClientSession() as sess:
            # I hope this is legal.
            async with sess.get(
                f"https://osu.ppy.sh/web/osu-getosufile.php?q={id}",
                headers={"user-agent": "osu!"},
            ) as resp:

                if not await resp.text():
                    log.fail(
                        f"Couldn't fetch the .osu file of {id}. Maybe because api rate limit?"
                    )
                    return b""

                async with aiofiles.open(f".data/beatmaps/{id}.osu", "w+") as osu:
                    await osu.write(await resp.text())


@glob.osu.add_endpoint("/web/osu-osz2-getscores.php")
@check_auth("us", "ha")
async def get_scores(req: Request):
    """
    Return format:
    {0}|false|{1}|{2}|{3}
    {0}
    [bold:0,size:20]{0}|{1}
    {0}
    {0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}|{9}|{10}|{11}|{12}|{13}|{14}|{15} # Personal Best and top 50 scores

    {0} = Beatmap Status
    false/true = Server has OSZ2 file (Must set to "false" to allow score submission)
    {1} = Beatmap ID
    {2} = Beatmap Set ID
    {3} = Total Plays

    {0} = Beatmap Offset

    {0} = Artist Unicide
    {1} = Title Unicode

    {0} = Rating

    {0} = Score ID
    {1} = Username
    {2} = Score
    {3} = Combo
    {4} = 50s
    {5} = 100s
    {6} = 300s
    {7} = Misses
    {8} = Katus
    {9} = Gekis
    {10} = Perfect
    {11} = Mod Used
    {12} = User ID
    {13} = Rank Position on Beatmap
    {14} = Date Played (Unix)
    {15} = Has replay saved on server
    """
    hash = req.get_args["c"]
    mode = int(req.get_args["m"])

    if not hash in glob.beatmaps:
        b = await Beatmap.get_beatmap(hash, req.get_args["i"])
    else:
        b = glob.beatmaps[hash]

    if not b:
        if not hash in glob.beatmaps:
            glob.beatmaps[hash] = b

        return b"-1|true"

    if not hash in glob.beatmaps:
        b.approved += 1

    if b.approved - 1 <= 0:
        if not hash in glob.beatmaps:
            glob.beatmaps[hash] = b

        return b"0|false"

    p = glob.players.get_user(req.get_args["us"])

    if not p:
        return b""

    # pretty sus
    if not int(req.get_args["mods"]) & Mods.RELAX and p.relax:
        p.relax = False

    if int(req.get_args["mods"]) & Mods.RELAX and not p.relax:
        p.relax = True

    ret = b.web_format
    order = ("score", "pp")[int(p.relax)]

    if b.approved >= 1:
        if not (
            data := await glob.sql.fetch(
                "SELECT id FROM scores WHERE user_id = %s "
                "AND relax = %s AND hash_md5 = %s AND mode = %s "
                f"AND status = 3 ORDER BY {order} DESC LIMIT 1",
                (p.id, p.relax, b.hash_md5, mode),
            )
        ):
            ret += "\n"
        else:
            s = await Score.set_data_from_sql(data["id"])

            ret += s.web_format

        # this caching method is pretty scuffed
        # it doesn't really work the way i want
        # and i'm not really sure how i can make
        # it so it does work the way i want, i'll
        # be working on this another time, but
        # it still works

        async for play in glob.sql.iterall(
            "SELECT s.id FROM scores s INNER JOIN users u ON u.id = s.user_id "
            "WHERE s.hash_md5 = %s AND s.mode = %s AND s.relax = %s AND s.status = 3 "
            f"AND u.privileges & 4 ORDER BY s.{order} DESC, s.submitted ASC LIMIT 50",
            (b.hash_md5, mode, p.relax),
        ):
            ls: Score = await Score.set_data_from_sql(play["id"])

            await ls.calculate_position()

            ls.map.scores += 1

            ret += ls.web_format

    asyncio.create_task(get_beatmap_file(b.map_id))

    if not hash in glob.beatmaps:
        glob.beatmaps[hash] = b

    return ret  # placeholder


@glob.osu.add_endpoint("/web/osu-submit-modular-selector.php", methods=["POST"])
async def score_submission(req: Request):
    if (ver := req.post_args["osuver"])[:4] != "2021":
        return b"error: oldver"

    submission_key = f"osu!-scoreburgr---------{ver}"

    s: Score = await Score.set_data_from_submission(
        req.post_args["score"], req.post_args["iv"], 
        submission_key, int(req.post_args["x"])
    )

    if not s or not (passed := s.status >= SubmitStatus.PASSED):
        return b"error: no"

    if not s.player:
        return b"error: nouser"

    if not s.map:
        return b"error: beatmap"

    # i hate this
    s.id = await glob.sql.fetch("SELECT id FROM scores ORDER BY id DESC LIMIT 1")
    if not s.id:
        s.id = 1
    else:
        s.id = s.id["id"] + 1

    s.play_time = req.post_args["st" if passed else "ft"]

    # handle needed things, if the map is ranked.
    if s.map.approved >= 1:
        if not s.player.is_restricted:
            s.map.plays += 1

            if passed:
                s.map.passes += 1

                # restrict the player if they
                # somehow managed to submit a
                # score without a replay.
                if "score" not in req.files.keys():
                    await s.player.restrict()
                    return b"error: no"

                with open(f".data/replays/{s.id}.osr", "wb+") as file:
                    file.write(req.files["score"])

                await glob.sql.execute(
                    "UPDATE beatmaps SET plays = %s, passes = %s WHERE hash = %s",
                    (s.map.plays, s.map.passes, s.map.hash_md5),
                )

    await s.save_to_db()

    if passed:
        stats = s.player

        # check if the user is playing for the first time
        prev_stats = None

        if stats.total_score > 0:
            prev_stats = copy.copy(stats)

        # calculate new stats
        if s.map.approved >= 1:

            stats.playcount += 1
            stats.total_score += s.score

            if s.status == SubmitStatus.BEST:
                table = ("stats", "stats_rx")[s.relax]

                rank = await glob.sql.fetch(
                    f"SELECT COUNT(*) AS rank FROM {table} t "
                    "INNER JOIN users u ON u.id = t.id "
                    "WHERE t.id != %s AND t.pp_std > %s "
                    "ORDER BY t.pp_std DESC, t.total_score_std DESC LIMIT 1",
                    (stats.id, stats.pp),
                )

                stats.rank = rank["rank"] + 1

                sus = s.score

                if s.pb:
                    sus -= s.pb.score

                stats.ranked_score += sus

                scores = await glob.sql.fetchall(
                    "SELECT pp, accuracy FROM scores "
                    "WHERE user_id = %s AND mode = %s "
                    "AND status = 3 AND relax = %s",
                    (stats.id, s.mode.value, s.relax),
                )

                avg_accuracy = np.array([x[1] for x in scores])

                stats.accuracy = float(np.mean(avg_accuracy))

                weighted = np.sum(
                    [score[0] * 0.95 ** (place) for place, score in enumerate(scores)]
                )
                weighted += 416.6667 * (1 - 0.9994 ** len(scores))
                stats.pp = math.ceil(weighted)

                asyncio.create_task(s.player.update_stats(s.mode, s.relax))

                if s.position == 1 and not stats.is_restricted:
                    modes = {0: "osu!", 1: "osu!taiko", 2: "osu!catch", 3: "osu!mania"}[
                        s.mode
                    ]

                    chan: Channel = glob.channels.get_channel("#announce")

                    await chan.send(f"{s.player.embed} achieved #1 on {s.map.embed} ({modes}) [{'RX' if s.relax else 'VN'}]", sender=glob.bot)

        if not s.relax:

            ret: list = []

            ret.append(
                "|".join(
                    (
                        f"beatmapId:{s.map.map_id}",
                        f"beatmapSetId:{s.map.set_id}",
                        f"beatmapPlaycount:{s.map.plays}",
                        f"beatmapPasscount:{s.map.passes}",
                        f"approvedDate:{s.map.approved_date}",
                    )
                )
            )

            ret.append(
                "|".join(
                    (
                        "chartId:beatmap",
                        f"chartUrl:{s.map.url}",
                        "chartName:deez nuts",
                        *(
                            (
                                Beatmap.add_chart("rank", None, s.position),
                                Beatmap.add_chart("accuracy", None, s.accuracy),
                                Beatmap.add_chart("maxCombo", None, s.max_combo),
                                Beatmap.add_chart("rankedScore", None, s.score),
                                Beatmap.add_chart("totalScore", None, s.score),
                                Beatmap.add_chart("pp", None, math.ceil(s.pp)),
                            )
                            if not s.pb
                            else (
                                Beatmap.add_chart("rank", s.pb.position, s.position),
                                Beatmap.add_chart("accuracy", s.pb.accuracy, s.accuracy),
                                Beatmap.add_chart("maxCombo", s.pb.max_combo, s.max_combo),
                                Beatmap.add_chart("rankedScore", s.pb.score, s.score),
                                Beatmap.add_chart("totalScore", s.pb.score, s.score),
                                Beatmap.add_chart(
                                    "pp", math.ceil(s.pb.pp), math.ceil(s.pp)
                                ),
                            )
                        ),
                        f"onlineScoreId:{s.id}",
                    )
                )
            )

            ret.append(
                "|".join(
                    (
                        "chartId:overall",
                        f"chartUrl:{s.player.url}",
                        "chartName:penis",
                        *(
                            (
                                Beatmap.add_chart("rank", None, stats.rank),
                                Beatmap.add_chart("accuracy", None, stats.accuracy),
                                Beatmap.add_chart("maxCombo", None, 0),
                                Beatmap.add_chart("rankedScore", None, stats.ranked_score),
                                Beatmap.add_chart("totalScore", None, stats.total_score),
                                Beatmap.add_chart("pp", None, stats.pp),
                            )
                            if not prev_stats
                            else (
                                Beatmap.add_chart("rank", prev_stats.rank, stats.rank),
                                Beatmap.add_chart(
                                    "accuracy", prev_stats.accuracy, stats.accuracy
                                ),
                                Beatmap.add_chart("maxCombo", 0, 0),
                                Beatmap.add_chart(
                                    "rankedScore",
                                    prev_stats.ranked_score,
                                    stats.ranked_score,
                                ),
                                Beatmap.add_chart(
                                    "totalScore", prev_stats.total_score, stats.total_score
                                ),
                                Beatmap.add_chart("pp", prev_stats.pp, stats.pp),
                            )
                        ),
                        # achievements can wait
                        f"achievements-new:osu-combo-500+deez+nuts",
                    )
                )
            )

            asyncio.create_task(run.run_anticheat(s, f".data/replays/{s.id}.osr", f".data/beatmaps/{s.map.map_id}.osu"))
        else: return b"error: no"
    else: return b"error: no"

    return "\n".join(ret).encode()


@glob.osu.add_endpoint("/web/osu-getreplay.php")
@check_auth("u", "h")
async def get_replay(req: Request):
    async with aiofiles.open(f".data/replays/{req.get_args['c']}.osr", "rb") as raw:
        if replay := await raw.read():
            return replay

    return b""


@glob.osu.add_endpoint("/web/osu-comment.php", methods=["POST"])
@check_auth("u", "p", method="POST")
async def get_beatmap_comments(req: Request):
    if not req.post_args:
        return b""

    log.info(req.post_args)
    return b""
