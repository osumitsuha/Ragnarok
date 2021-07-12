from enum import IntFlag, unique


@unique
class SlotStatus(IntFlag):
    OPEN = 1
    LOCKED = 2
    NOTREADY = 4
    READY = 8
    NOMAP = 16
    PLAYING = 32
    COMPLETE = 64
    OCCUPIED = NOTREADY | READY | NOMAP | PLAYING | COMPLETE
    QUIT = 128


@unique
class SlotTeams(IntFlag):
    NEUTRAL = 0
    BLUE = 1
    RED = 2


@unique
class TeamType(IntFlag):
    HEAD2HEAD = 0
    TAG_COOP = 1
    TEAM_VS = 2
    TAG_TV = 3  # tag team vs


@unique
class ScoringType(IntFlag):
    SCORE = 0
    ACC = 1
    COMBO = 2
    SCORE_V2 = 3

    @classmethod
    def find_value(cls, name: str) -> int:
        c = cls(0)

        if name == "sv2":
            return c.__class__.SCORE_V2

        if name.upper() in c.__class__.__dict__:
            return c.__class__.__dict__[name.upper()]
