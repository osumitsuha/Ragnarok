"""
from objects.player import Player

class Players:
    def __init__(self, p: Player, host: bool = False):
        self.player = p
        self.host = host
"""
class Match:
    def __init__(self): ...
    #async def change_host(self, p: Player): ...

class Matches:
    def __init__(self):
        self.matches: Match = []

    async def remove_match(self, m: Match):
        if m in self.matches:
            self.matches.remove(m)

    async def find_match(self, match_id: int):
        for match in self.matches:
            if match_id == match.id:
                return match

    async def create_match(self, m: Match):
        self.matches.append(m)
