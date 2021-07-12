from typing import TYPE_CHECKING, Any, Union

from objects import glob
from objects.channel import Channel
from objects.match import Match
from objects.player import Player


class Tokens:
    def __init__(self):
        self.players: list[Player] = []

    def add_user(self, p: Player) -> None:
        self.players.append(p)

    def remove_user(self, p: Player) -> None:
        self.players.remove(p)

    def get_user(self, value: Union[str, int]) -> Player:
        for p in self.players:
            if (
                p.id == value
                or p.username == value
                or p.token == value
                or p.safe_name == value
            ):
                return p

    async def get_user_offline(self, value: Union[str, int]) -> Player:
        if p := self.get_user(value):
            return p

        if p := await self.from_sql(value):
            return p

    async def from_sql(self, value: Union[str, int]) -> Player:
        data = await glob.sql.fetch(
            "SELECT username, id, privileges, passhash FROM users "
            "WHERE (id = %s OR username = %s OR safe_username = %s)",
            (value, value, value),
        )

        if not data:
            return

        p = Player(**data)

        return p

    def enqueue(self, packet: bytes) -> None:
        for p in self.players:
            p.enqueue(packet)


class Channels:
    def __init__(self):
        self.channels: list[Channel] = []

    def add_channel(self, data: dict[str, Any]) -> None:
        self.channels.append(Channel(**data))

    def remove_channel(self, c: Channel) -> None:
        self.channels.remove(c)

    def get_channel(self, name: str) -> Channel:
        for chan in self.channels:
            if chan._name == name:
                return chan


class Matches:
    def __init__(self):
        self.matches: "Match" = []

    async def remove_match(self, m: "Match"):
        if m in self.matches:
            self.matches.remove(m)

    async def find_match(self, match_id: int):
        for match in self.matches:
            if match_id == match.match_id:
                return match

    async def add_match(self, m: "Match"):
        self.matches.append(m)
