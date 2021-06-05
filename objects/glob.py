from objects.player import Player
from objects.tokens import Tokens
from objects.channel import Channel, Channels
from config import config

registered_routes: list = []
registered_packets: list = []
registered_osu_routes: list = []
registered_commands: list = []

prefix: str = "!"

config: dict = config

sql = None

bcrypt_cache: dict = {}

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

debug: bool = config["debug"]

players: list[Player] = Tokens()

channels: list[Channel] = Channels()

osu_key: str = config["osu_api_key"]