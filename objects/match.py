from constants.match import SlotStatus, SlotTeams, TeamType, ScoringType
from objects.channel import Channel
from constants.playmode import Mode
from constants.mods import Mods
from packets import writer
from objects import glob


class Players:
    def __init__(self):
        self.p = None  # no superman :pensive:
        self.mods: Mods = Mods.NONE
        self.host: bool = False
        self.status: SlotStatus = SlotStatus.OPEN
        self.team: SlotTeams = SlotTeams.NEUTRAL
        self.loaded: bool = False

    def reset(self):
        self.p = None
        self.mods = Mods.NONE
        self.host = False
        self.status = SlotStatus.OPEN
        self.team = SlotTeams.NEUTRAL
        self.loaded = False

    def copy_from(self, old):
        self.p = old.p
        self.mods = old.mods
        self.host = old.host
        self.status = old.status
        self.team = old.team
        self.loaded = old.loaded


class Match:
    def __init__(self):
        self.match_id: int = 0
        self.match_name: str = ""
        self.match_pass: str = ""

        self.host = None
        self.in_progress: bool = False

        self.map_id: int = 0
        self.map_title: str = ""
        self.map_md5: str = ""

        self.slots: Players = [Players() for _ in range(0, 16)]

        self.mode: Mode = Mode.OSU
        self.mods: Mods = Mods.NONE
        self.freemods: bool = False

        self.scoring_type: ScoringType = ScoringType.SCORE
        self.pp_win_condition: bool = True
        self.team_type: TeamType = TeamType.HEAD2HEAD

        self.seed: int = 0

        self.connected: list = []

        self.chat: Channel = None

    def __repr__(self):
        return f"MATCH-{self.match_id}"

    def get_free_slot(self):
        for id, slot in enumerate(self.slots):
            if slot.status == SlotStatus.OPEN:
                return id

    def find_host(self):
        for slot in self.slots:
            if slot.p.id == self.host:
                return slot

    def find_user(self, p):
        for slot in self.slots:
            if slot.p == p:
                return slot

    def find_user_slot(self, p):
        for id, slot in enumerate(self.slots):
            if slot.p == p:
                return id

    def find_slot(self, slot_id):
        for id, slot in enumerate(self.slots):
            if id == slot_id:
                return slot

    async def transfer_host(self, slot):
        self.host = slot.p.id
        slot.host = True
        
        slot.p.enqueue(await writer.MatchTransferHost())

        self.enqueue(await writer.Notification(f"{slot.p.username} became host!"))

        await self.enqueue_state()

    async def enqueue_state(self, immune: set[int] = set(), lobby: bool = False):
        for p in self.connected:
            if p.id not in immune:
                p.enqueue(await writer.MatchUpdate(self))

        if lobby:
            chan = glob.channels.get_channel("#lobby")
            chan.enqueue(await writer.MatchUpdate(self))

    def enqueue(self, data, lobby: bool = False):
        for p in self.connected:
            p.enqueue(data)

        if lobby:
            chan = glob.channels.get_channel("#lobby")
            chan.enqueue(data)
