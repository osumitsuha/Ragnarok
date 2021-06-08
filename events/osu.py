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
import aiofiles
import aiohttp
import time
import math
import os

def check_auth(u: str, pw: str):
    def decorator(cb: Callable) -> Callable:
        @wraps(cb)
        async def wrapper(req, *args, **kwargs):
            player = req.query_params[u]
            password = req.query_params[pw]

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
    # beatmap_id = req.query_params["i"]

    if not hash in glob.beatmaps:
        b = await Beatmap.get_beatmap(hash)
    else:
        b = glob.beatmaps[hash]

    if not b:
        return Response("-1|true")
        
    if b.approved <= 0:
        return Response("0|false")

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

        # any() with b.scores doesn't work.
        # its annoying.
        missing_mode = False
        missing_relax = False

        for score in b.scores:
            if score[1] != mode:
                missing_mode = True

            if score[2] != int(p.relax):
                missing_relax = True

        if len(b.scores) == 0:
            missing_mode = True

        if missing_mode or missing_relax:
            if glob.debug:
                log.debug(f"Caching scores for [mode: {mode} | relax: {p.relax}] for {b.full_title}")

            # I'm not sure, if this is how 
            # I will be handling leaderboards 
            # since I feel like it looks weird,

            async for play in glob.sql.iterall(
                "SELECT id FROM scores WHERE hash_md5 = %s "
                "AND mode = %s AND relax = %s AND status = 3 "
                f"ORDER BY {order} DESC, submitted ASC LIMIT 50",
                (b.hash_md5, mode, p.relax)
            ):
                
                ls = await Score.set_data_from_sql(play["id"])

                await ls.calculate_position() 

                # {0} is the web format for the score
                # {1} is the mode of the play
                # {2} is the indicator that the play is either relax or not.
                b.scores.append([ls.web_format, mode, ls.relax])

    # fetched leaderboards
    fl = (x[0] for x in b.scores if x[1] == mode and x[2] == p.relax)

    ret += "".join(fl)

    if not os.path.exists(f".data/beatmaps/{b.file}"):
        async with aiohttp.ClientSession() as sess:
            async with sess.get(f"https://old.ppy.sh/osu/{b.map_id}") as resp:
                async with aiofiles.open(f".data/beatmaps/{b.file}", "w+") as osu:
                    await osu.write(await resp.text())

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

    leaderboard = []

    # i hate this
    s.id = await glob.sql.fetch("SELECT id FROM scores ORDER BY id DESC LIMIT 1") 
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

                # Leaderboard cache handling
                for position in s.map.scores:
                    if (position[1] == s.mode and position[2] == s.relax):
                        leaderboard.append(position[0])

                # TODO: top 50 handling

                leaderboard.append([s.web_format, s.mode, s.relax])

                if s.position == 1 and s.status == SubmitStatus.BEST:
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

                await glob.sql.execute(
                    "UPDATE beatmaps SET "
                    "plays = %s, passes = %s "
                    "WHERE hash = %s",
                    (s.map.plays, s.map.passes, s.map.hash_md5)
                )
            else:
                return Response("error: no")

    if s.passed:
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

            *(
                Beatmap.add_chart("rank", s.position),
                Beatmap.add_chart("accuracy", s.accuracy),
                Beatmap.add_chart("maxCombo", s.max_combo),
                Beatmap.add_chart("rankedScore", s.score),
                Beatmap.add_chart("totalScore", s.score),
                Beatmap.add_chart("pp", math.ceil(s.pp))
            ),

            f"onlineScoreId:{s.id}"
        )))

        ret.append("|".join((
            "chartId:overall",
            f"chartUrl:{s.player.url}",
            "chartName:penis",

            *(
                Beatmap.add_chart("rank", s.player.rank),
                Beatmap.add_chart("accuracy", s.accuracy),
                Beatmap.add_chart("maxCombo", 0),
                Beatmap.add_chart("rankedScore", s.score),
                Beatmap.add_chart("totalScore", s.score),
                Beatmap.add_chart("pp", s.player.pp)
            ),

            # achievements can wait
            f"achievements-new:osu-combo-500+deez+nuts"
        )))
    else:
        return Response("error: no")

    await s.save_to_db()

    return Response("\n".join(ret))

@register_osu("osu-getreplay.php")
@check_auth("u", "h")
async def get_replay(req: Request):
    async with aiofiles.open(f".data/replays/{req.query_params['c']}.osr", "rb") as raw:
        if (replay := await raw.read()):
            return Response(replay)

        return Response("")

@register_osu("osu-comment", method="POST")
async def get_beatmap_comments(req: Request):
    body = await req.form()
    log.debug(body)
