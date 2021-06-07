from objects.player import Player
from objects.score import Score
from hashlib import md5
from packets import writer
from objects import glob
import struct

async def write_replay(replay, s = None, score_id = 0) -> None:
    raw = await replay.read()

    if score_id and not s:
        play = await glob.sql.fetch(
            "SELECT s.id, s.user_id, s.hash_md5, s.score, s.pp, s.count_300, "
            "s.count_50, s.count_geki, s.count_katu, s.count_miss, s.count_100, "
            "s.max_combo, s.accuracy, s.perfect, s.rank, s.mods, s.passed, "
            "s.exited, s.play_time, s.mode, s.submitted, s.relax FROM scores s "
            "WHERE s.id = %s LIMIT 1"
            (score_id)
        )

        user_info = await glob.sql.fetch(
            "SELECT username, id, privileges, passhash "
            "FROM users WHERE id = %s",
            (play["user_id"])
        )

        s = Score(p=Player(**user_info), **play)


    r_hash = md5(
        f"{s.count_100 + s.count_300}o{s.count_50}o{s.count_geki}o"
        f"{s.count_katu}t{s.count_miss}a{s.map.hash_md5}r{s.max_combo}e"
        f"{bool(s.perfect)}y{s.player.username}o{s.score}u{s.position}{s.mods}True"
        .encode()
    ).hexdigest()

    ret = bytearray()

    ret += struct.pack("<b", s.mode)
    ret += await writer.write_int32(20210520) # we just gonna use the latest version of osu
    
    ret += await writer.write_str(s.map.hash_md5) + \
           await writer.write_str(s.player.username) + \
           await writer.write_str(r_hash)

    ret += struct.pack(
        "<hhhhhhih?i", 
        s.count_300, s.count_100, s.count_50, s.count_geki,
        s.count_katu, s.count_miss, s.score, s.max_combo,
        s.perfect, s.mods
    )
    
    ret += await writer.write_str("")
    
    ret += struct.pack("<qi", s.submitted, len(raw))
    ret += raw

    ret += struct.pack("<q", s.id)

    return ret

# Maybe this will be useful in the future?
# For an anticheat maybe?
class ParseReplay:
    def __init__(self, replay: bytes): ...
