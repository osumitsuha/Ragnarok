from enum import unique, IntEnum

@unique
class PresenceFilter(IntEnum):
    NIL = 0
    ALL = 1
    FRIENDS = 2