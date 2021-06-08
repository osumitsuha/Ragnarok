from objects.player import Player
from objects import glob

class Tokens:
    def __init__(self):
        self.players: list[Player] = []

    async def add_user(self, p: Player) -> None:
        self.players.append(p)

    async def remove_user(self, p: Player) -> None:
        self.players.remove(p)

    async def get_user(self, value):
        for p in self.players:
            if p.id == value \
            or p.username == value \
            or p.token == value \
            or p.safe_name == value:
                return p

    async def get_user_offline(self, value) -> Player:
        if (p := await self.get_user(value)):
            return p
        
        if (p := await self.from_sql(value)):
            return p


    async def from_sql(self, value):
        data = await glob.sql.fetch(
            "SELECT username, id, privileges, passhash FROM users "
            "WHERE (id = %s OR username = %s OR safe_username = %s)", 
            (value, value, value)
        )

        if not data:
            return

        data["ip"] = "127.0.0.1"
        p = Player(**data)

        return p

    def enqueue(self, packet: bytes) -> None:
        for p in self.players:
            p.enqueue(packet)
