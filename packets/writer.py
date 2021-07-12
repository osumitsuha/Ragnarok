from constants.player import Ranks, Privileges
from constants.packets import BanchoPackets
from constants.match import SlotStatus
from typing import Any, TYPE_CHECKING
from enum import unique, IntEnum
from objects import glob
import struct
import math

if TYPE_CHECKING:
    from objects.match import Match
    from objects.player import Player
    from objects.score import ScoreFrame

spec = ("<b", "<B", "<h", "<H", "<i", "<I", "<f", "<q", "<Q", "<d")


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

    match = 13

    byte = 100
    ubyte = 110

    int32_list = 10
    string = 19
    raw = 20

    multislots = 21
    multislotsmods = 22

    message = 23


async def write_uleb128(value: int) -> bytearray:
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


async def write_byte(value: int) -> bytearray:
    return bytearray(struct.pack("<b", value))


async def write_ubyte(value: int) -> bytearray:
    return bytearray(struct.pack("<B", value))


async def write_int32(value: int) -> bytearray:
    return bytearray(value.to_bytes(Types.int32, "little", signed=True))


async def write_int32_list(values: tuple[int]) -> bytearray:
    data = bytearray(len(values).to_bytes(2, "little"))

    for value in values:
        data += value.to_bytes(4, "little")

    return data


async def write_multislots(slots) -> bytearray:
    ret = bytearray()

    ret.extend([s.status for s in slots])
    ret.extend([s.team for s in slots])

    for slot in slots:
        if slot.status & SlotStatus.OCCUPIED:
            ret += slot.p.id.to_bytes(4, "little")

    return ret


async def write_multislotsmods(slots) -> bytearray:
    ret = bytearray()

    for slot in slots:
        ret += slot.mods.to_bytes(4, "little")

    return ret


async def write_str(string: str) -> bytearray:
    if not string:
        return bytearray(b"\x00")

    data = bytearray(b"\x0B")

    data += await write_uleb128(len(string.encode()))
    data += string.encode()
    return data


async def write_msg(sender: str, msg: str, chan: str, id: int) -> bytearray:
    ret = bytearray()

    ret += await write_str(sender)
    ret += await write_str(msg)
    ret += await write_str(chan)
    ret += id.to_bytes(4, "little", signed=True)

    return ret


async def write(pID: int, *args: tuple[Any, ...]) -> bytes:
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
        elif d_type == Types.multislots:
            data += await write_multislots(args)
        elif d_type == Types.multislotsmods:
            data += await write_multislotsmods(args)
        elif d_type == Types.byte:
            data += await write_byte(args)
        elif d_type == Types.ubyte:
            data += await write_ubyte(args)
        elif d_type == Types.message:
            data += await write_msg(*args)
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
    return await write(BanchoPackets.CHO_USER_ID, (id, Types.int32))


async def UsrJoinSpec(id: int) -> bytes:
    return await write(BanchoPackets.CHO_SPECTATOR_JOINED, (id, Types.int32))


async def UsrLeftSpec(id: int) -> bytes:
    return await write(BanchoPackets.CHO_SPECTATOR_LEFT, (id, Types.int32))


async def FellasJoinSpec(id: int) -> bytes:
    return await write(BanchoPackets.CHO_FELLOW_SPECTATOR_JOINED, (id, Types.int32))


async def FellasLeftSpec(id: int) -> bytes:
    return await write(BanchoPackets.CHO_FELLOW_SPECTATOR_LEFT, (id, Types.int32))


async def UsrCantSpec(id: int) -> bytes:
    return await write(BanchoPackets.CHO_SPECTATOR_CANT_SPECTATE, (id, Types.int32))


async def Notification(msg: str) -> bytes:
    return await write(BanchoPackets.CHO_NOTIFICATION, (msg, Types.string))


async def UserPriv(privileges: int) -> bytes:
    rank = Ranks.NORMAL
    rank |= Ranks.SUPPORTER

    if privileges & Privileges.BAT:
        rank |= Ranks.BAT

    if privileges & Privileges.MODERATOR:
        rank |= Ranks.FRIEND

    if privileges & Privileges.ADMIN:
        rank |= Ranks.FRIEND

    if privileges & Privileges.DEV:
        rank |= Ranks.PEPPY

    return await write(BanchoPackets.CHO_PRIVILEGES, (rank, Types.int32))


async def ProtocolVersion(version: int) -> bytes:
    return await write(BanchoPackets.CHO_PROTOCOL_VERSION, (version, Types.int32))


async def UpdateFriends(friends_id: tuple[int]):
    return await write(BanchoPackets.CHO_FRIENDS_LIST, (friends_id, Types.int32_list))


async def UpdateStats(p: "Player") -> bytes:
    if p not in glob.players.players:
        return b""

    return await write(
        BanchoPackets.CHO_USER_STATS,
        (p.id, Types.int32),
        (p.status.value, Types.uint8),
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
        (math.ceil(p.pp), Types.int16),
    )


async def UserPresence(p: "Player") -> bytes:
    if p not in glob.players.players:
        return b""

    rank = Ranks.NONE

    if p.privileges & Privileges.VERIFIED:
        rank |= Ranks.NORMAL

    if p.privileges & Privileges.BAT:
        rank |= Ranks.BAT

    if p.privileges & Privileges.SUPPORTER:
        rank |= Ranks.SUPPORTER

    if p.privileges & Privileges.MODERATOR:
        rank |= Ranks.FRIEND

    if p.privileges & Privileges.ADMIN:
        rank |= Ranks.FRIEND

    if p.privileges & Privileges.DEV:
        rank |= Ranks.PEPPY

    return await write(
        BanchoPackets.CHO_USER_PRESENCE,
        (p.id, Types.int32),
        (p.username, Types.string),
        (p.timezone, Types.byte),
        (p.country, Types.ubyte),
        (rank, Types.byte),
        (p.longitude, Types.float32),
        (p.latitude, Types.float32),
        (p.rank, Types.int32),
    )


async def MainMenuIcon() -> bytes:
    return await write(
        BanchoPackets.CHO_MAIN_MENU_ICON,
        ("https://imgur.com/Uihzw6N.png|https://c.mitsuha.pw", Types.string),
    )


async def ChanJoin(name: str) -> bytes:
    return await write(BanchoPackets.CHO_CHANNEL_JOIN_SUCCESS, (name, Types.string))


async def ChanKick(name: str) -> bytes:
    return await write(BanchoPackets.CHO_CHANNEL_KICK, (name, Types.string))


async def ChanAutoJoin(chan: str) -> bytes:
    return await write(BanchoPackets.CHO_CHANNEL_AUTO_JOIN, (chan, Types.string))


async def ChanInfo(name: str) -> bytes:
    if not (c := glob.channels.get_channel(name)):
        return bytes()

    return await write(
        BanchoPackets.CHO_CHANNEL_INFO,
        (c.name, Types.string),
        (c.description, Types.string),
        (len(c.connected), Types.int32),
    )


async def ChanInfoEnd() -> bytes:
    return await write(BanchoPackets.CHO_CHANNEL_INFO_END)


async def ServerRestart() -> bytes:
    return await write(BanchoPackets.CHO_RESTART, (0, Types.int32))


async def SendMessage(sender: str, message: str, channel: str, id: int) -> bytes:
    return await write(
        BanchoPackets.CHO_SEND_MESSAGE,
        ((sender, message, channel, id), Types.message),
    )


async def Logout(id: int) -> bytes:
    return await write(
        BanchoPackets.CHO_USER_LOGOUT,
        (id, Types.int32),
        (0, Types.uint8),
    )


async def FriendsList(*ids: list[int]) -> bytes:
    return await write(BanchoPackets.CHO_FRIENDS_LIST, (ids, Types.int32_list))


def get_match_struct(m: "Match", send_pass: bool = False) -> bytes:
    struct = [
        (m.match_id, Types.int16),
        (m.in_progress, Types.int8),
        (0, Types.byte),
        (m.mods, Types.uint32),
        (m.match_name, Types.string),
    ]

    if m.match_pass:
        if send_pass:
            struct.append((m.match_pass, Types.string))
        else:
            struct.append(("trollface", Types.string))
    else:
        struct.append(("", Types.string))

    struct.extend(
        (
            (m.map_title, Types.string),
            (m.map_id, Types.int32),
            (m.map_md5, Types.string),
            (m.slots, Types.multislots),
            (m.host, Types.int32),
            (m.mode.value, Types.byte),
            (m.scoring_type.value, Types.byte),
            (m.team_type.value, Types.byte),
            (m.freemods, Types.byte),
        )
    )

    if m.freemods:
        struct.append((m.slots, Types.multislotsmods))

    struct.append((m.seed, Types.int32))

    return struct


async def Match(m: "Match") -> bytes:
    struct = get_match_struct(m)
    return await write(BanchoPackets.CHO_NEW_MATCH, *struct)


async def MatchAllReady() -> bytes:
    return await write(BanchoPackets.CHO_MATCH_ALL_PLAYERS_LOADED)


async def MatchComplete():
    return await write(BanchoPackets.CHO_MATCH_COMPLETE)


async def MatchDispose(mid: int) -> bytes:
    return await write(BanchoPackets.CHO_DISPOSE_MATCH, (mid, Types.int32))


async def MatchFail() -> bytes:
    return await write(BanchoPackets.CHO_MATCH_JOIN_FAIL)


async def MatchInvite(m: "Match", p: "Player", reciever) -> bytes:
    return await write(
        BanchoPackets.CHO_MATCH_INVITE,
        ((p.username, f"#multi_{m.match_id}", reciever, p.id), Types.message),
    )


async def MatchJoin(m: "Match") -> bytes:
    struct = get_match_struct(m, send_pass=True)
    return await write(BanchoPackets.CHO_MATCH_JOIN_SUCCESS, *struct)


async def MatchPassChange(pwd: str) -> bytes:
    return await write(BanchoPackets.CHO_MATCH_CHANGE_PASSWORD, (pwd, Types.string))


async def MatchPlayerFailed(pid: int) -> bytes:
    return await write(BanchoPackets.CHO_MATCH_PLAYER_FAILED, (pid, Types.int32))


async def MatchScoreUpdate(s: "ScoreFrame", slot_id: int, raw_data: bytes) -> bytes:
    ret = bytearray(b"0\x00\x00")

    ret += len(raw_data).to_bytes(4, "little")

    ret += s.time.to_bytes(4, "little", signed="True")
    ret += struct.pack("<b", slot_id)

    ret += struct.pack(
        "<HHHHHH",
        s.count_300,
        s.count_100,
        s.count_50,
        s.count_geki,
        s.count_katu,
        s.count_miss,
    )

    ret += s.score.to_bytes(4, "little", signed=True)

    ret += struct.pack("<HH", s.max_combo, s.combo)

    ret += struct.pack("<bbbb", s.perfect, s.current_hp, s.tag_byte, s.score_v2)

    return ret


async def MatchPlayerReqSkip(pid: id) -> bytes:
    return await write(BanchoPackets.CHO_MATCH_PLAYER_SKIPPED, (pid, Types.int32))


async def MatchSkip() -> bytes:
    return await write(BanchoPackets.CHO_MATCH_SKIP)


async def MatchStart(m: "Match") -> bytes:
    struct = get_match_struct(m, send_pass=True)
    return await write(BanchoPackets.CHO_MATCH_START, *struct)


async def MatchTransferHost() -> bytes:
    return await write(BanchoPackets.CHO_MATCH_TRANSFER_HOST)


async def MatchUpdate(m: "Match") -> bytes:
    struct = get_match_struct(m, send_pass=True)
    return await write(BanchoPackets.CHO_UPDATE_MATCH, *struct)


async def Pong() -> bytes:
    return await write(BanchoPackets.CHO_PONG)
