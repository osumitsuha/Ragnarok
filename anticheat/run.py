from anticheat.utils.beatmap import Beatmap
from osrparse import parse_replay
from constants.mods import Mods
from utils.replay import write_replay


async def run_anticheat(score, score_file_name: int, beatmap_file_name: str):
    r = parse_replay(await write_replay(s=score, file_name=score_file_name))

    hitobjects = await Beatmap().parse_hitobjects(
        beatmap_file_name, hr=r.mod_combination & Mods.HARDROCK
    )

    c_aim = 0
    for aim in r.play_data:
        aim.xy = aim.x + aim.y

        for obj in hitobjects:
            if aim.x == obj.x and aim.y == obj.y:
                c_aim += 1

    # I'm not 100% sure, if this works or not lol

    # print(f"{c_aim} / {len(hitobjects)} * 100 = {c_aim / len(hitobjects) * 100}")
