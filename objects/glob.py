from typing import Union, Any, Callable, Pattern, TYPE_CHECKING
from lenhttp import Router, LenHTTP
from lib.database import Database
from config import conf
import re

if TYPE_CHECKING:
    from objects.collections import Tokens, Channels, Matches
    from constants.commands import Command
    from objects.beatmap import Beatmap
    from objects.player import Player
    from packets.reader import Packet


server: LenHTTP = None

debug: bool = conf["server"]["debug"]
domain: str = conf["server"]["domain"]
port: int = conf["server"]["port"]

bancho: Router = None
avatar: Router = None
osu: Router = None

packets: dict[int, 'Packet'] = {}
tasks: list[dict[str, Callable]] = []

bot: 'Player' = None

prefix: str = "!"

config: dict[str, Union[dict[str, Any], str, bool]] = conf

sql: Database = None

bcrypt_cache: dict[str, str] = {}

title_card: str = '''
                . . .o .. o
                    o . o o.o
                        ...oo.
                   ________[]_
            _______|_o_o_o_o_o\___
            \\""""""""""""""""""""/
             \ ...  .    . ..  ./
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
osu!ragnarok, an osu!bancho & /web/ emulator.
Simon & Aoba
'''


players: 'Tokens' = None

channels: 'Channels' = None

matches: 'Matches' = None

osu_key: str = config["osu_api_key"]

beatmaps: dict[str, 'Beatmap'] = {}

regex: dict[str, Pattern[str]] = {
    "np": re.compile(r"^ACTION|https://osu.mitsuha.pw/beatmapsets/[0-9].*#/(\d*)") # taken from kurrikku cause i cant regex lol
}