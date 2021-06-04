import struct
from utils import log
from packets.writer import Types

def read_packet(data: bytes, structure: tuple):
    reader = Reader(data)

    data = {}

    for struct in structure:
        type = struct[1] # data type

        ret = b""

        if type == Types.int8:
            ret = reader.read_int8()
        elif type == Types.uint8:
            ret = reader.read_uint8()
        elif type == Types.int16:
            ret = reader.read_int16()
        elif type == Types.uint16:
            ret = reader.read_int16()
        elif type == Types.int32:
            ret = reader.read_int32()
        elif type == Types.uint32:
            ret = reader.read_uint32()
        elif type == Types.int64:
            ret = reader.read_int64()
        elif type == Types.uint64:
            ret = reader.read_uint64()

        elif type == Types.byte:
            ret = reader.read_bytes()

        elif type == Types.string:
            ret = reader.read_str()
        elif type == Types.float32:
            ret = reader.read_float32()
        elif type == Types.float64:
            ret = reader.read_float64()
        elif type == Types.int32_list:
            ret = reader.read_i32_list()
        elif type == Types.raw:
            ret = reader.read_raw()
        else:
            log.error("Type: %s; has not yet been implemented" % (type))
            return b""

        data[struct[0]] = ret

    return data
        

class Reader:
    def __init__(self, packet_data: bytes):
        self.packet_data = packet_data
        self.offset = 0
        self.packet_id, self.length = self.get_packet_length_und_id()

    def read_bytes(self):
        ret = struct.unpack("<b", self.packet_data[self.offset:self.offset+1])
        self.offset += 1
        return ret[0]
    
    def read_unsigned_bytes(self):
        ret = struct.unpack("<B", self.packet_data[self.offset:self.offset+1])
        self.offset += 1
        return ret[0]

    def read_int8(self):
        ret = struct.unpack("<i", self.packet_data[self.offset:self.offset+1])
        self.offset += 1
        return ret[0]

    def read_int16(self):
        ret = struct.unpack("<i", self.packet_data[self.offset:self.offset+2])
        self.offset += 2
        return ret[0]

    def read_int32(self):
        ret = struct.unpack("<i", self.packet_data[self.offset:self.offset+4])
        self.offset += 4
        return ret[0]

    def read_int64(self):
        ret = struct.unpack("<i", self.packet_data[self.offset:self.offset+8])
        self.offset += 8
        return ret[0]
    
    def read_uint8(self):
        ret = struct.unpack("<I", self.packet_data[self.offset:self.offset+1])
        self.offset += 1
        return ret[0]

    def read_uint16(self):
        ret = struct.unpack("<I", self.packet_data[self.offset:self.offset+2])
        self.offset += 2
        return ret[0]

    def read_uint32(self):
        ret = struct.unpack("<I", self.packet_data[self.offset:self.offset+4])
        self.offset += 4
        return ret[0]

    def read_uint64(self):
        ret = struct.unpack("<I", self.packet_data[self.offset:self.offset+8])
        self.offset += 8
        return ret[0]

    def read_i32_list(self) -> tuple[int]:
        length = self.read_short() #i16

        ret = struct.unpack(f"<{'I' * length[0]}", self.packet_data[self.offset:self.offset+length[0]*4]) #i32
        self.offset += length[0] * 4
        return ret

    def read_float32(self) -> float:
        ret = struct.unpack('<f', self.packet_data[self.offset:self.offset+4])
        self.offset += 4
        return ret

    def read_float64(self) -> float:
        ret = struct.unpack('<d', self.packet_data[self.offset:self.offset+8])
        self.offset += 8
        return ret

    def read_short(self):
        ret = struct.unpack("<h", self.packet_data[self.offset:self.offset+2])
        self.offset += 2
        return ret

    def get_packet_length_und_id(self):
        ret = struct.unpack("<HxI", self.packet_data[self.offset:self.offset+7])
        self.offset += 7
        return ret[0], ret[1]

    def _read_uleb128(self, value):
        shift = 0
        arr = [0,0]	#total, length
        b = 0

        while True:
            b = value[arr[1]]
            arr[1]+=1
            arr[0] |= int(b & 127) << shift
            if b & 128 == 0:
                break
            shift += 7

        return arr

    # what the fuck is this code
    def read_str(self):
        value = self._read_uleb128(self.packet_data[self.offset+1:])

        ret = self.packet_data[self.offset+value[1]:self.offset+value[0]+value[1]+1][1:].decode()
        if ret == "\x00":
            return b""

        self.offset += value[0]+value[1]+1
        return ret

    def _read_raw(self, length: int):
        ret = self.packet_data[self.offset:self.offset+length]
        self.offset += length
        return ret

    def read_raw(self):
        ret = self.packet_data[self.offset:self.offset+self.length]
        self.offset += self.length
        return ret