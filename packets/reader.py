from typing import AnyStr, Callable, Iterator
from constants.packets import BanchoPackets
from objects.score import ScoreFrame
from constants.playmode import Mode
from dataclasses import dataclass
from objects.match import Match
from constants.mods import Mods
from constants.match import *
from objects import glob
from utils import log
import struct

IGNORED_PACKETS = [4, 79]

@dataclass
class Packet:
    packet: BanchoPackets

    callback: Callable
    restricted: bool

class Reader:
    def __init__(self, packet_data: bytes):
        self.packet_data = memoryview(packet_data)
        self.offset = 0
        self.packet, self.plen = None, 0

    def __iter__(self) -> Iterator:
        return self

    def __next__(self) -> Packet:
        while self.data:
            self.packet, self.plen = self.read_headers()

            if self.packet not in glob.packets:
                if glob.debug and self.packet not in IGNORED_PACKETS:
                    log.warn(
                        f"Packet <{self.packet}> has been requested although it's an unregistered packet."
                    )

                if self.plen != 0:
                    self.offset += self.plen
            else:
                break
        else:
            raise StopIteration

        self.packet = BanchoPackets(self.packet)

        return glob.packets[self.packet.value]

    def read_headers(self) -> tuple[BanchoPackets, int]:
        if len(self.data) < 7:
            raise StopIteration

        ret = struct.unpack("<HxI", self.data[:7])
        self.offset += 7
        return ret[0], ret[1]

    @property
    def data(self):
        return self.packet_data[self.offset:]

    def read_byte(self) -> int:
        ret = struct.unpack("<b", self.data[:1])
        self.offset += 1
        return ret[0]

    def read_ubyte(self) -> int:
        ret = struct.unpack("<B", self.data[:1])
        self.offset += 1
        return ret[0]

    def read_int8(self) -> int:
        ret = int.from_bytes(self.data[:1], "little", signed=True)
        self.offset += 1
        return ret  - 256 if ret > 127 else ret

    def read_uint8(self) -> int:
        ret = int.from_bytes(self.data[:1], "little", signed=False)
        self.offset += 1
        return ret

    def read_int16(self) -> int:
        ret = int.from_bytes(self.data[:2], "little", signed=True)
        self.offset += 2
        return ret

    def read_uint16(self) -> int:
        ret = int.from_bytes(self.data[:2], "little", signed=False)
        self.offset += 2
        return ret

    def read_int32(self) -> int:
        ret = int.from_bytes(self.data[:4], "little", signed=True)
        self.offset += 4
        return ret

    def read_uint32(self) -> int:
        ret = int.from_bytes(self.data[:4], "little", signed=False)
        self.offset += 4
        return ret

    def read_int64(self) -> int:
        ret = int.from_bytes(self.data[:8], "little", signed=True)
        self.offset += 8
        return ret

    def read_uint64(self) -> int:
        ret = int.from_bytes(self.data[:8], "little", signed=False)
        self.offset += 8
        return ret

    def read_i32_list(self) -> tuple[int]:
        length = self.read_int16()

        ret = struct.unpack(
            f"<{'I' * length}", self.data[:length * 4]
        ) 
        
        self.offset += length * 4
        return ret

    def read_float32(self) -> float:
        ret = struct.unpack("<f", self.data[:4])
        self.offset += 4
        return ret

    def read_float64(self) -> float:
        ret = struct.unpack("<d", self.data[:8])
        self.offset += 8
        return ret

    def read_str(self) -> str:
        self.offset += 1

        shift = 0
        result = 0

        while True:
            b = self.data[0]
            self.offset += 1

            result |= (b & 0x7F) << shift

            if b & 0x80 == 0:
                break

            shift += 7

        ret = self.data[:result].tobytes().decode()

        self.offset += result
        return ret

    def _read_raw(self, length: int) -> AnyStr:
        ret = self.data[:length]
        self.offset += length
        return ret

    def read_raw(self) -> AnyStr:
        ret = self.data[:self.plen]
        self.offset += self.plen
        return ret

    def read_match(self) -> Match:
        m = Match()

        m.match_id = len(glob.matches.matches)

        self.offset += 2

        m.in_progress = self.read_int8()

        self.read_int8()  # ignore match type; 0 = normal osu!, 1 = osu! arcade

        m.mods = Mods(self.read_int32())

        m.match_name = self.read_str()
        m.match_pass = self.read_str()

        m.map_title = self.read_str()
        m.map_id = self.read_int32()
        m.map_md5 = self.read_str()

        for slot in m.slots:
            slot.status = SlotStatus(self.read_int8())

        for slot in m.slots:
            slot.team = SlotTeams(self.read_int8())

        for slot in m.slots:
            if slot.status & SlotStatus.OCCUPIED:
                self.offset += 4

        m.host = self.read_int32()

        m.mode = Mode(self.read_int8())
        m.scoring_type = ScoringType(self.read_int8())
        m.team_type = TeamType(self.read_int8())

        m.freemods = self.read_int8() == 1

        if m.freemods:
            for slot in m.slots:
                slot.mods = Mods(self.read_int32())

        m.seed = self.read_int32()

        return m

    def read_scoreframe(self) -> ScoreFrame:
        s = ScoreFrame()

        s.time = self.read_int32()
        s.id = self.read_byte()

        s.count_300 = self.read_uint16()
        s.count_100 = self.read_uint16()
        s.count_50 = self.read_uint16()
        s.count_geki = self.read_uint16()
        s.count_katu = self.read_uint16()
        s.count_miss = self.read_uint16()

        s.score = self.read_int32()
        
        s.max_combo = self.read_uint16()
        s.combo = self.read_uint16()

        s.perfect = self.read_int8()

        s.current_hp = self.read_byte()
        s.tag_byte = self.read_byte()

        s.score_v2 = self.read_int8()

        return s
