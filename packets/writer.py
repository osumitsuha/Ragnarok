from typing import Any, Union
from enum import unique, IntEnum
from objects import glob
from utils import log
from constants.packets import BanchoPackets
from functools import cache
import struct

spec = (
    '<b', '<B',
    '<h', '<H',
    '<i', '<I', '<f',
    '<q', '<Q', '<d' 
)

@unique
class Types(IntEnum):
    int8 = 0
    uint8 = 1
    int16 = 2
    uint16 = 3
    int32 = 4
    uint32 = 5
    float32 = 6
    int64 = 7
    uint64 = 8
    float64 = 9
    
    message        = 11
    channel        = 12
    match          = 13
    scoreframe     = 14
    mapInfoRequest = 15
    mapInfoReply   = 16

    byte = 100

    int32_list   = 10
    int32_list4l = 18
    string     = 19
    raw        = 20

async def write_uleb128(
    value: int
) -> bytearray:
    if value == 0:
        return bytearray(b"\x00")

    data: bytearray = bytearray()
    length: int = 0

    while value > 0:
        data.append(value & 0x7F)
        value >>= 7
        if value != 0:
            data[length] |= 0x80

        length += 1

    return data

async def write_int32(
    value: int
) -> bytearray:
    return bytearray(value.to_bytes(Types.int32, "little", signed=True))

async def write_int32_list(
    values: tuple[int]
) -> bytearray:
    data = bytearray(len(values).to_bytes(2, 'little')) #i16

    for value in values:
        data += value.to_bytes(4, 'little') #i32

    return data

async def write_str(
    string: str
) -> bytearray:
    if not string:
        return bytearray(b"\x00")
    
    data = bytearray(b"\x0B")

    data += await write_uleb128(len(string.encode()))
    data += string.encode()
    return data

async def write(
    pID: int, 
    *args: tuple[Any, ...]
) -> bytes:
    data = bytearray(struct.pack("<Hx", pID))

    for args, d_type in args:
        if d_type == Types.string:
            data += await write_str(args)
        elif d_type == Types.raw:
            data += args
        elif d_type == Types.int32:
            data += await write_int32(args)
        elif d_type == Types.int32_list:
            data += await write_int32_list(args)
        else:
            data += struct.pack(spec[d_type], args)

    data[3:3] += struct.pack("<I", len(data) - 3)
    return bytes(data)

async def UserID(id: int) -> bytes:
    """
    ID Responses:
    -1: Authentication Failure
    -2: Old Client
    -3: Banned (due to breaking the game rules)
    -4: Banned (due to account deactivation)
    -5: An error occurred
    -6: Needs Supporter
    -7: Password Reset
    -8: Requires Verification
    > -1: Valid ID
    """
    return await write(
        BanchoPackets.CHO_USER_ID,
        (id, Types.int32)
    )

async def UsrJoinSpec(id: int) -> bytes:
    return await write(
        BanchoPackets.CHO_SPECTATOR_JOINED,
        (id, Types.int32)
    )

async def UsrLeftSpec(id: int) -> bytes:
    return await write(
        BanchoPackets.CHO_SPECTATOR_LEFT,
        (id, Types.int32)
    )

async def FellasJoinSpec(id: int) -> bytes:
    return await write(
        BanchoPackets.CHO_FELLOW_SPECTATOR_JOINED,
        (id, Types.int32)
    )

async def FellasLeftSpec(id: int) -> bytes:
    return await write(
        BanchoPackets.CHO_FELLOW_SPECTATOR_LEFT,
        (id, Types.int32)
    )

async def UsrCantSpec(id: int) -> bytes:
    return await write(
        BanchoPackets.CHO_SPECTATOR_CANT_SPECTATE,
        (id, Types.int32)
    )

async def SpecFramesData(data: bytes) -> bytes:
    return await write(
        BanchoPackets.CHO_SPECTATE_FRAMES,
        (data, Types.raw)
    )

async def Notification(msg: str) -> bytes:
    return await write(
        BanchoPackets.CHO_NOTIFICATION,
        (msg, Types.string)
    )

async def UserPriv(rank: int) -> bytes:
    return await write(
        BanchoPackets.CHO_PRIVILEGES,
        (rank, Types.int32)
    )

async def ChanJoin(chan: str) -> bytes:
    return await write(
        BanchoPackets.CHO_CHANNEL_AUTO_JOIN,
        (chan, Types.string)
    )

async def ChanInfo(name: str) -> bytes:
    if not (c := glob.channels.get_channel(name)):
        return bytes()

    return await write(
        BanchoPackets.CHO_CHANNEL_INFO,
        (c.name, Types.string),
        (c.description, Types.string),
        (c.players_len, Types.uint16)
    )

async def ChanInfoEnd() -> bytes:
    return await write(
        BanchoPackets.CHO_CHANNEL_INFO_END
    )

async def ProtocolVersion(version: int) -> bytes:
    return await write(
        BanchoPackets.CHO_PROTOCOL_VERSION,
        (version, Types.int32)
    )

async def UpdateFriends(friends_id: tuple[int]):
    return await write(
        BanchoPackets.CHO_FRIENDS_LIST,
        (friends_id, Types.int32_list)
    )

async def UpdateStats(p):
    if p not in glob.players.players:
        return b""

    return await write(
        BanchoPackets.CHO_USER_STATS,
        (p.id, Types.int32),
        (p.status, Types.uint8),
        (p.status_text, Types.string),
        (p.beatmap_md5, Types.string),
        (p.current_mods, Types.int32),
        (p.play_mode, Types.uint8),
        (p.beatmap_id, Types.int32),
        (p.ranked_score, Types.int64),
        (p.accuracy / 100.0, Types.float32),
        (p.playcount, Types.int32),
        (p.total_score, Types.int64),
        (p.rank, Types.int32),
        (p.pp, Types.int16)
    )

async def UserPresence(p):
    if p not in glob.players.players:
        return b""

    return await write(
        BanchoPackets.CHO_USER_PRESENCE,
        (p.id, Types.int32),
        (p.username, Types.string),
        (p.timezone, Types.int32),
        (p.country, Types.int32),
        (p.privileges, Types.int32),
        (p.longitude, Types.float32),
        (p.latitude, Types.float32),
        (p.rank, Types.int32),
    )

async def MainMenuIcon():
    return await write(
        BanchoPackets.CHO_MAIN_MENU_ICON,
        ("https://ainu.pw/static/images/image0_1.jpg|", Types.string)
    )
    
async def ChanJoinSuccess(name):
    return await write(
        BanchoPackets.CHO_CHANNEL_JOIN_SUCCESS,
        (name, Types.string)
    )

async def ChanKick(name):
    return await write(
        BanchoPackets.CHO_CHANNEL_KICK,
        (name, Types.string)
    )

async def ServerRestart():
    return await write(
        BanchoPackets.CHO_RESTART,
        (0, Types.int32)
    )

async def SendMessage(sender, message, channel):
    return await write(
        BanchoPackets.CHO_SEND_MESSAGE,
        (sender, Types.string),
        (message, Types.string),
        (channel, Types.string)
    )

async def Logout(id):
    return await write(
        BanchoPackets.CHO_USER_LOGOUT,
        (id, Types.int32),
        (0, Types.uint8),
    )

async def FriendsList(*ids):
    return await write(
        BanchoPackets.CHO_FRIENDS_LIST,
        (ids, Types.int32_list)
    )
