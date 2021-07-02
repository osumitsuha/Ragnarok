from enum import IntEnum


class Approved(IntEnum):
    GRAVEYARD = -2
    WIP = -1
    PENDING = 0

    RANKED = 1
    APPROVED = 2
    QUALIFIED = 3
    LOVED = 4
