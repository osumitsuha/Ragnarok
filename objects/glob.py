from objects.player import Player
from objects.tokens import Tokens
from objects.channel import Channel, Channels
from config import config

registered_routes: list = []
registered_packets: list = []
registered_osu_routes: list = []

config = config

sql = None

bcrypt_cache = {}

players: list[Player] = Tokens()

channels: list[Channel] = Channels()

osu_key = config["osu_api_key"]