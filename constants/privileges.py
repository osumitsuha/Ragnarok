from enum import unique, IntEnum

@unique
class Privileges(IntEnum):
    BANNED = 1 << 0
    
    USER = 1 << 1
    VERIFIED = 1 << 2

    SUPPORTER = 1 << 3

    BAT = 1 << 4
    MODERATOR = 1 << 5
    ADMIN = 1 << 6
    DEV = 1 << 7 

    