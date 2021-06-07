from starlette.requests import Request
from starlette.responses import Response
from objects.beatmap import Beatmap
from constants.mods import Mods
from objects.player import Player
from objects import glob
from utils import log
from decorators import register_osu, check_auth, register
from objects.score import Score
from utils import replay
import aiofiles
import time

@register("/web/{url:str}", methods=["GET", "POST"])
async def handle_osu(req: Request):
    if req.url._url.startswith("https://osu.mitsuha.pw"):
        for route in glob.registered_osu_routes:
            if route["route"] == req.path_params["url"]:
                if route["method"] != req.method:
                    return Response("")

                return await route["func"](req)

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
    start = time.time_ns()

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

    if b.approved >= 1:
        if not (data := await glob.sql.fetch(
            "SELECT s.id, s.hash_md5, s.score, s.pp, s.count_300, s.count_100, "
            "s.count_50, s.count_geki, s.count_katu, s.count_miss, "
            "s.max_combo, s.accuracy, s.perfect, s.rank, s.mods, s.passed, "
            "s.exited, s.play_time, s.mode, s.submitted, s.relax FROM scores s "
            "INNER JOIN beatmaps b ON b.hash = s.hash_md5 WHERE s.user_id = %s "
            "AND s.relax = %s AND b.hash = %s AND s.mode = %s AND s.passed = 1 "
            "ORDER BY s.score DESC LIMIT 1",
            (p.id, p.relax, b.hash_md5, mode)
        )):
            ret += "\n"
        else:
            data["map"] = b

            s = Score(p=p, **data)

            s.position = 0

            if not p.is_restricted:
                await s.calculate_position() 

            ret += s.web_format

        # this caching method is pretty scuffed
        # it doesn't really work the way i want
        # and i'm not really sure how i can make
        # it so it does work the way i want, i'll
        # be working on this another time, but
        # it still works; edit: i made it work 
        # the way i want.

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
                "SELECT s.id, s.user_id, s.hash_md5, s.score, s.pp, s.count_300, s.count_100, "
                "s.count_50, s.count_geki, s.count_katu, s.count_miss, "
                "s.max_combo, s.accuracy, s.perfect, s.rank, s.mods, s.passed, "
                "s.exited, s.play_time, s.mode, s.submitted, s.relax FROM scores s "
                "INNER JOIN beatmaps b ON b.hash = s.hash_md5 "
                "INNER JOIN users u ON u.id = s.user_id "
                "WHERE b.hash = %s AND s.mode = %s AND s.relax = %s AND u.privileges & 4 AND s.passed = 1 "
                "ORDER BY s.score DESC, s.submitted ASC LIMIT 50",
                (b.hash_md5, mode, p.relax)
            ):
                d = await glob.sql.fetch("SELECT username, id, privileges, passhash FROM users WHERE id = %s", (play["user_id"]))
                
                d["ip"] = "127.0.0.1"
                play["map"] = b

                lp = Player(**d)
                ls = Score(p=lp, **play)

                await ls.calculate_position() 

                # {0} is the web format for the score
                # {1} is the mode of the play
                # {2} is the indicator that the play is either relax or not.
                b.scores.append([ls.web_format, mode, ls.relax])

    # fetched leaderboards
    fl = (x[0] for x in b.scores if x[1] == mode and x[2] == p.relax)

    ret += "".join(fl)

    if not hash in glob.beatmaps:
        glob.beatmaps[hash] = b

    if glob.debug:
        log.debug(f"It took {(time.time_ns() - start) / 1e6}ms to load the leaderboard")

    return Response(ret) #placeholder

@register_osu("osu-submit-modular-selector.php", method="POST")
async def score_submission(req: Request):
    # TODO: chart
    start = time.time_ns()

    body = await req.form()

    if not body.get("osuver").startswith("2021"):
        return Response("error: oldver")

    submission_key = f"osu!-scoreburgr---------{body['osuver']}"

    s = await Score.set_data_from_submission(
        body.multi_items()[2][1], body["iv"], 
        submission_key, int(body["x"]), int(body["ft"])
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

    # handle needed things, if the map is ranked.
    if s.map.approved >= 1:
        if not s.player.is_restricted:
            if s.passed:
                await s.calculate_position() 
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

            # Maybe this needs to be done a
            # different way? Well see till then.
            if s.position == 1:
                modes = {
                    0: "osu!",
                    1: "osu!taiko",
                    2: "osu!catch",
                    3: "osu!mania"
                }[s.mode]

                await glob.channels.message(
                    await glob.players.get_user_by_id(1), 
                    f"{s.player.embed} achieved #1 on {s.map.embed} ({modes}) [{'RX' if s.relax else 'VN'}]",
                    "#announce"
                )

    await s.save_to_db()

    if glob.debug:
        log.debug(f"Submit handler took: {(time.time_ns() - start) / 1e6}ms")

    return Response("error: ban")

@register_osu("osu-getreplay.php")
@check_auth("u", "h")
async def get_replay(req: Request):
    async with aiofiles.open(f".data/replays/{req.query_params['c']}.osr", "rb") as raw:
        if (replay := await raw.read()):
            return Response(replay)

        return Response("")

@register_osu("osu-comment", method="POST")
async def get_beatmap_comments(req: Request): ...
