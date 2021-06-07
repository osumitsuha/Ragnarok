from enum import unique, IntEnum

@unique
class Mode(IntEnum):
    OSU = 0
    TAIKO = 1
    CATCH = 2
    MANIA = 3