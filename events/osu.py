from starlette.requests import Request
from starlette.responses import Response
from objects.beatmap import Beatmap
from constants.mods import Mods
from objects import glob
from utils import log
from decorators import register_osu, register
from objects.score import Score, SubmitStatus
from typing import Callable
from functools import wraps
import numpy as np
import aiofiles
import aiohttp
import asyncio
import time
import math
import os
import copy

def check_auth(u: str, pw: str, method="GET"):
    def decorator(cb: Callable) -> Callable:
        @wraps(cb)
        async def wrapper(req, *args, **kwargs):
            if method == "GET":
                player = req.query_params[u]
                password = req.query_params[pw]
            else:
                body = await req.form()
                player = body[u]
                password = body[pw]

            if not (p := await glob.players.get_user(player)):
                return Response("")

            if p.passhash in glob.bcrypt_cache:
                if password.encode("utf-8") != glob.bcrypt_cache[p.passhash]:
                    return Response("")

            return await cb(req, *args, **kwargs)

        return wrapper

    return decorator

@register("/web/{url:str}", methods=["GET", "POST"])
async def handle_osu(req: Request):
    if req.url._url.startswith("https://osu.mitsuha.pw"):
        start = time.time_ns()
        for route in glob.registered_osu_routes:
            if route["route"] == req.path_params["url"]:
                if route["method"] != req.method:
                    return Response("")

                resp = await route["func"](req)
                
                log.info(f"[{req.method}] /web/{req.path_params['url']} - {round((time.time_ns() - start) / 1e6, 2)}ms")
                return resp
    
        log.error(f"[{req.method}] /web/{req.path_params['url']} - {round((time.time_ns() - start) / 1e6, 2)}ms")
        return Response("")

async def get_beatmap_file(id: int):
    if not os.path.exists(f".data/beatmaps/{id}.osu"):
        async with aiohttp.ClientSession() as sess:
            # I hope this is legal.
            async with sess.get(
                    f"https://osu.ppy.sh/web/osu-getosufile.php?q={id}", 
                    headers={"user-agent": "osu!"}
                ) as resp:

                if not await resp.text():
                    log.error(f"Couldn't fetch the .osu file of {id}. Maybe because api rate limit?")
                    return Response("")

                async with aiofiles.open(f".data/beatmaps/{id}.osu", "w+") as osu:
                    await osu.write(await resp.text())

@register_osu("osu-osz2-getscores.php")
@check_auth("us", "ha")
async def get_scores(req: Request):
    """
        Return format:
        {0}|false|{1}|{2}|{3}
        {0}
        [bold:0,size:20]{0}|{1}
        {0}
        {0}|{1}|{2}|{3s}|{4}|{5}|{6}|{7}|{8}|{9}|{10}|{11}|{12}|{13}|{14}|{15} # Personal Best and top 50 scores

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
    hash = req.query_params["c"]
    mode = int(req.query_params["m"])

    if not hash in glob.beatmaps:
        b = await Beatmap.get_beatmap(hash, req.query_params["i"])
    else:
        b = glob.beatmaps[hash]

    if not b:
        return Response("-1|true")
        
    if b.approved <= 0:
        return Response("0|false")

    if not hash in glob.beatmaps:
        b.approved += 1

    p = await glob.players.get_user(req.query_params["us"])

    if not p:
        return Response("")

    # pretty sus
    if not int(req.query_params["mods"]) & Mods.RELAX and p.relax:
        p.relax = False

    if int(req.query_params["mods"]) & Mods.RELAX and not p.relax:
        p.relax = True

    ret = b.web_format
    order = ("score", "pp")[int(p.relax)]

    if b.approved >= 1:
        if not (data := await glob.sql.fetch(
            "SELECT id FROM scores WHERE user_id = %s "
            "AND relax = %s AND hash_md5 = %s AND mode = %s "
            f"AND status = 3 ORDER BY {order} DESC LIMIT 1",
            (p.id, p.relax, b.hash_md5, mode)
        )):
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
            (b.hash_md5, mode, p.relax)
        ):
            ls = await Score.set_data_from_sql(play["id"])

            await ls.calculate_position() 

            ls.map.scores += 1

            ret += ls.web_format

    asyncio.create_task(get_beatmap_file(b.map_id))

    if not hash in glob.beatmaps:
        glob.beatmaps[hash] = b

    return Response(ret) #placeholder

@register_osu("osu-submit-modular-selector.php", method="POST")
async def score_submission(req: Request):
    body = await req.form()

    if not body.get("osuver").startswith("2021"):
        return Response("error: oldver")

    submission_key = f"osu!-scoreburgr---------{body['osuver']}"

    s = await Score.set_data_from_submission(
        body.multi_items()[2][1], body["iv"], 
        submission_key, int(body["x"]), body["s"]
    )

    if not s:
        return Response("error: no")

    if not s.player:
        return Response("error: nouser")

    if not s.map:
        return Response("error: beatmap")

    if not s.passed:
        ret = "error: no"


    # i hate this
    s.id = await glob.sql.fetch("SELECT id FROM scores ORDER BY id DESC LIMIT 1") 
    if not s.id:
        s.id = 1
    else:
        s.id = s.id["id"] + 1

    s.play_time = body["st" if s.passed else "ft"]

    # handle needed things, if the map is ranked.
    if s.map.approved >= 1:
        if not s.player.is_restricted:
            s.map.plays += 1

            if s.passed:
                s.map.passes += 1

                # restrict the player if they
                # somehow managed to submit a 
                # score without a replay.
                if body.multi_items()[-1][0] != "score":
                    await s.player.restrict()
                    return Response("error: no")

                async with aiofiles.open(f".data/replays/{s.id}.osr", "wb+") as file:
                    await file.write(await body["score"].read())

                await glob.sql.execute(
                    "UPDATE beatmaps SET "
                    "plays = %s, passes = %s "
                    "WHERE hash = %s",
                    (s.map.plays, s.map.passes, s.map.hash_md5)
                )

    await s.save_to_db()

    if s.passed:
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
                        (stats.id, stats.pp)
                    )

                stats.rank = rank["rank"] + 1
                
                sus = s.score

                if s.pb:
                    sus -= s.pb.score

                stats.ranked_score += sus

                scores = await glob.sql.fetchall(
                    "SELECT pp, accuracy FROM scores "
                    "WHERE user_id = %s AND mode = %s "
                    "AND status = 3", (stats.id, s.mode.value)
                )

                avg_accuracy = np.array([x[1] for x in scores])

                stats.accuracy = float(np.mean(avg_accuracy))

                weighted = np.sum([score[0] * 0.95 ** (place - 1) for place, score in enumerate(scores)])
                weighted += 416.6667 * (1 - 0.9994 ** len(scores))
                stats.pp = math.ceil(weighted)

                if s.position == 1 and not stats.is_restricted:
                    modes = {
                        0: "osu!",
                        1: "osu!taiko",
                        2: "osu!catch",
                        3: "osu!mania"
                    }[s.mode]

                    await glob.channels.message(
                        await glob.players.get_user(1), 
                        f"{s.player.embed} achieved #1 on {s.map.embed} ({modes}) [{'RX' if s.relax else 'VN'}]",
                        "#announce"
                    )

        ret = []

        ret.append("|".join((
            f"beatmapId:{s.map.map_id}",
            f"beatmapSetId:{s.map.set_id}",
            f"beatmapPlaycount:{s.map.plays}",
            f"beatmapPasscount:{s.map.passes}",
            f"approvedDate:{s.map.approved_date}"
        )))

        ret.append("|".join((
            "chartId:beatmap",
            f"chartUrl:{s.map.url}",
            "chartName:deez nuts",

            *((
                Beatmap.add_chart("rank", None, s.position),
                Beatmap.add_chart("accuracy", None, s.accuracy),
                Beatmap.add_chart("maxCombo", None, s.max_combo),
                Beatmap.add_chart("rankedScore", None, s.score),
                Beatmap.add_chart("totalScore", None, s.score),
                Beatmap.add_chart("pp", None, math.ceil(s.pp))
            ) if not s.pb else (
                Beatmap.add_chart("rank", s.pb.position, s.position),
                Beatmap.add_chart("accuracy", s.pb.accuracy, s.accuracy),
                Beatmap.add_chart("maxCombo", s.pb.max_combo, s.max_combo),
                Beatmap.add_chart("rankedScore", s.pb.score, s.score),
                Beatmap.add_chart("totalScore", s.pb.score, s.score),
                Beatmap.add_chart("pp", math.ceil(s.pb.pp), math.ceil(s.pp))
            )),

            f"onlineScoreId:{s.id}"
        )))

        ret.append("|".join((
            "chartId:overall",
            f"chartUrl:{s.player.url}",
            "chartName:penis",

            *((
                Beatmap.add_chart("rank", None, stats.rank),
                Beatmap.add_chart("accuracy", None, stats.accuracy),
                Beatmap.add_chart("maxCombo", None, 0),
                Beatmap.add_chart("rankedScore", None, stats.ranked_score),
                Beatmap.add_chart("totalScore", None, stats.total_score),
                Beatmap.add_chart("pp", None, stats.pp)
            ) if not prev_stats else (
                Beatmap.add_chart("rank", prev_stats.rank, stats.rank),
                Beatmap.add_chart("accuracy", prev_stats.accuracy, stats.accuracy),
                Beatmap.add_chart("maxCombo", 0, 0),
                Beatmap.add_chart("rankedScore", prev_stats.ranked_score, stats.ranked_score),
                Beatmap.add_chart("totalScore", prev_stats.total_score, stats.total_score),
                Beatmap.add_chart("pp", prev_stats.pp, stats.pp)
            )),

            # achievements can wait
            f"achievements-new:osu-combo-500+deez+nuts"
        )))
    else:
        return Response("error: no")


    return Response("\n".join(ret))

@register_osu("osu-getreplay.php")
@check_auth("u", "h")
async def get_replay(req: Request):
    async with aiofiles.open(f".data/replays/{req.query_params['c']}.osr", "rb") as raw:
        if (replay := await raw.read()):
            return Response(replay)

        return Response("")

@register_osu("osu-comment.php", method="POST")
@check_auth("u", "p", method="POST")
async def get_beatmap_comments(req: Request):
    body = await req.form()

    if not body:
        return Response("")

    log.info(body)
    return Response("")
