from objects.player import Player

class Tokens:
    def __init__(self):
        self.players: list[Player] = []

    async def add_user(self, p: Player) -> None:
        self.players.append(p)

    async def remove_user(self, p: Player) -> None:
        self.players.remove(p)

    async def get_user(self, username: str) -> Player:
        for p in self.players:
            if p.username == username:
                return p

    async def get_user_by_id(self, id: int) -> Player:
        for p in self.players:
            if p.id == id:
                return p

    async def get_user_by_token(self, token: str) -> Player:
        for p in self.players:
            if p.token == token:
                return p

    def enqueue(self, packet: bytes) -> None:
        for p in self.players:
            p.enqueue(packet)
