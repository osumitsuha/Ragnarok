from starlette.requests import Request
from starlette.responses import Response
from objects.beatmap import Beatmap
from objects import glob
from utils import log
from decorators import register_osu, check_auth, register

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
        {0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}|{9}|{10}|{11}|{12}|{13}|{14}|{15} # Personal Best
        {0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}|{9}|{10}|{11}|{12}|{13}|{14}|{15} # Top 50 scores

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
    log.info(req.query_params)

    b = Beatmap(hash)

    if not await b.get_beatmap():
        return Response("-1|true")

    if b.approved <= 0:
        return Response("0|true")

    b.approved += 1

    ret = b.web_format
    ret += "\n1|Aoba|420|69|0|0|0|0|0|0|1|0|4|1|0|0" # personal best (change to "\n" if none)
    ret += "\n1|Aoba|420|69|0|0|0|0|0|0|1|0|4|1|0|0" # score 1
    ret += "\n2|Simon|69|88|1|2|3|0|4|5|0|8|3|2|0|0" # score 2

    return Response(ret) #placeholder
