import enum
import random

from abc import ABC
from hashlib import sha256
from typing import Type, Self, Any


#############################
# Local exception classes
#############################
class DMRPFieldOutOfRangeException(Exception):
    """
    Exception raised when a packet field value is out of the allowed or expected range.

    Attributes:
        field: The name or identifier of the problematic field.
        typename: The expected type or range description for the field.
    """
    def __init__(self, field, typename) -> None:
        super().__init__(f"Field out of range: {field} must be {typename}")


class DMRPUnknownPacketTypeException(Exception):
    """
    Exception raised when the packet factory cannot recognize the packet type
    from the given input data.
    """
    pass


class DMRPBadPacket(Exception):
    """
    Exception raised when a packet is structurally invalid or corrupted.
    """
    pass


#############################
# Functions
#############################
def calc_password_hash(salt: bytes, password: str) -> bytes:
    return sha256(salt + password.encode()).digest()


#############################
# Field classes
#############################
class DMRPFieldBase(ABC):
    def __init__(self, name: str, offset: int, bytelen: int) -> None:
        self.name, self.offset, self.bytelen = name, offset, bytelen
        self.eoffset = offset + bytelen
        self.typename = f"bytes{self.bytelen}"

    def __get__(self, obj, cls = None) -> Any:
        return bytes(obj._data[self.offset:self.eoffset])

    def __set__(self, obj, value: Any) -> None:
        if not isinstance(value, bytes) or self.bytelen != len(value):
            raise DMRPFieldOutOfRangeException(self.name, self.typename)
        obj._data[self.offset:self.eoffset] = value


class DMRPFieldBytes(DMRPFieldBase):
    def __get__(self, obj, cls = None) -> bytes:
        return super().__get__(obj, cls)

    def __set__(self, obj, value: bytes) -> None:
        super().__set__(obj, value)


class DMRPFieldStr(DMRPFieldBase):
    def __init__(self, name: str, offset: int, bytelen: int,
                 pad_with: bytes = b'\x20') -> None:
        super().__init__(name, offset, bytelen)
        self.typename = 'str'
        self.pad_with = pad_with

    def __get__(self, obj, cls = None) -> str:
        return (super().__get__(obj, cls).strip(b'\x20\x00')
                .decode(encoding='ascii', errors='ignore'))

    def __set__(self, obj, value: str) -> None:
        bvalue = value.encode()
        if len(bvalue) > self.bytelen:
            bvalue = bvalue[:self.bytelen]
        bvalue = bvalue.ljust(self.bytelen, self.pad_with)
        super().__set__(obj, bvalue)


class DMRPFieldInt(DMRPFieldBase):
    def __init__(self, name: str, offset: int, bytelen: int) -> None:
        super().__init__(name, offset, bytelen)
        self.typename = f"uint{str(bytelen * 8)}"

    def __get__(self, obj, cls = None) -> int:
        return int.from_bytes(super().__get__(obj, cls), byteorder="big")

    def __set__(self, obj, value: int) -> None:
        if not (0 <= value < 1<<(self.bytelen * 8)):
            raise DMRPFieldOutOfRangeException(self.name, self.typename)
        super().__set__(obj, value.to_bytes(self.bytelen, byteorder="big"))


class DMRPFieldPeerAuto(DMRPFieldInt):
    def fixoffset(self, offset: int) -> None:
        self.offset, self.eoffset = offset, offset + self.bytelen

    def __init__(self, name: str) -> None:
        super().__init__(name, 4, 4)

    def __get__(self, obj, cls = None) -> int:
        self.fixoffset(len(obj.PKT_TYPE))
        return super().__get__(obj, cls)

    def __set__(self, obj, value: int) -> None:
        self.fixoffset(len(obj.PKT_TYPE))
        super().__set__(obj, value)


#############################
# Packet classes hierarchy
#############################
class DMRPBasePacket(ABC):
    """
    Abstract base packet class.

    Derived packet class must redefine specific PKT_TYPE and PKT_SIZE
    class variables so that detect_by_data method works
    """
    PKT_TYPE: bytes = b""
    PKT_SIZE: int = 0

    def __init__(self, data: bytes|None = None) -> None:
        self._data: bytearray|None = None
        if data is None:
            self.create()
        else:
            self.from_data(data)

    def copy(self) -> Self:
        new_instance = self.__class__()  # Creates the same subclass
        if self._data is not None:
            new_instance._data = self._data[:]  # Copy the bytes
        return new_instance

    @classmethod
    def detect_by_data(cls, data: bytes) -> bool:
        """
        Detect, if this class can handle given data by matching PKT_TYPE to
        the data header prefix and PKT_SIZE to data length
        """
        if cls.PKT_SIZE != 0 and cls.PKT_SIZE != len(data):
            return False
        if cls.PKT_TYPE == b"":
            return False
        return data.startswith(cls.PKT_TYPE)

    def from_data(self, data: bytes) -> None:
        """
        Set inner data to raw data

        Args:
            data (bytes): The raw data from which to create a packet.

        Raises:
            DMRPBadPacket: if size or type doesn't match
        """
        self._data = None
        if not data.startswith(self.PKT_TYPE):
            raise DMRPBadPacket(
                f"Bad packet type: '{data[0:4]!r}', expected '{self.PKT_TYPE!r}'")
        if len(data) != self.PKT_SIZE:
            raise DMRPBadPacket(
                f"Bad packet size: {len(data)}, expected {self.PKT_SIZE}")
        self._data = bytearray(data)

    def create(self) -> None:
        """
        Create an empty data of the current packet type
        """
        self._data = bytearray(self.PKT_SIZE)
        if self.PKT_TYPE is not None:
            self._data[0:len(self.PKT_TYPE)] = self.PKT_TYPE

    def get_data(self) -> bytes:
        """
        Return raw data
        """
        if self._data is None:
            return b''
        return bytes(self._data)

    # pkt_type
    @property
    def pkt_type(self) -> str:
        if self.PKT_TYPE is None:
            return ""
        return self.PKT_TYPE.decode(encoding='ascii', errors='ignore')


class DMRPBasePeerPacket(DMRPBasePacket, ABC):
    """
    Abstract base class (more specific), which handles typical packets with
    type header and peer_id field
    """
    # peer_id
    peer_id: DMRPFieldInt = DMRPFieldPeerAuto('peer_id')

    def __str__(self) -> str:
        return f"{self.pkt_type} peer:{self.peer_id}"


class DMRPPacketLogin(DMRPBasePeerPacket):
    PKT_TYPE = b'RPTL'
    PKT_SIZE = 8


class DMRPPacketPing(DMRPBasePeerPacket):
    PKT_TYPE = b'RPTPING'
    PKT_SIZE = 11


class DMRPPacketPong(DMRPBasePeerPacket):
    PKT_TYPE = b'MSTPONG'
    PKT_SIZE = 11


class DMRPPacketMasterNoAck(DMRPBasePeerPacket):
    PKT_TYPE = b'MSTNAK'
    PKT_SIZE = 10


class DMRPPacketMasterClose(DMRPBasePeerPacket):
    PKT_TYPE = b'MSTCL'
    PKT_SIZE = 9


class DMRPPacketRepeaterClose(DMRPBasePeerPacket):
    PKT_TYPE = b'RPTCL'
    PKT_SIZE = 9


class DMRPPacketAck(DMRPBasePeerPacket):
    PKT_TYPE = b'RPTACK'
    PKT_SIZE = 10


class DMRPPacketSalt(DMRPBasePacket):
    PKT_TYPE = b'RPTACK'
    PKT_SIZE = 10

    salt = DMRPFieldBytes('salt', 6, 4)

    def set_random_salt(self) -> None:
        self.salt = random.randbytes(4)

    def __str__(self) -> str:
        return f"{self.pkt_type} salt:{self.salt.hex()}"


class DMRPPacketAuth(DMRPPacketLogin):
    PKT_TYPE = b'RPTK'
    PKT_SIZE = 40

    pass_hash = DMRPFieldBytes('pass_hash', 8, 32)

    def set_password_hash(self, salt: bytes, password: str) -> None:
        """
        Sets pass_hash field based on text password and salt bytes
        """
        self.pass_hash = calc_password_hash(salt, password)

    def check_password_hash(self, salt: bytes, password: str) -> bool:
        """
        Checks pass_hash field against given password and salt
        """
        return self.pass_hash == calc_password_hash(salt, password)

    def __str__(self) -> str:
        return (f"{self.pkt_type} peer:{self.peer_id} "
                f"pass_hash:{self.pass_hash.hex()}")


class DMRPPacketConfig(DMRPBasePeerPacket):
    PKT_TYPE = b'RPTC'
    PKT_SIZE = 302

    def create(self) -> None:
        self._data = bytearray(b'\x20' * self.PKT_SIZE)
        self._data[0:len(self.PKT_TYPE)] = self.PKT_TYPE

    callsign    = DMRPFieldStr('callsign', 8, 8)
    rx_freq     = DMRPFieldStr('rx_freq', 16, 9)
    tx_freq     = DMRPFieldStr('tx_freq', 25, 9)
    power       = DMRPFieldStr('power', 34, 2)
    color_code  = DMRPFieldStr('color_code', 36, 2)
    lat         = DMRPFieldStr('lat', 38, 8)
    lon         = DMRPFieldStr('lon', 46, 9)
    height      = DMRPFieldStr('height', 55, 3)
    location    = DMRPFieldStr('location', 58, 20)
    description = DMRPFieldStr('description', 78, 19)
    slots       = DMRPFieldStr('slots', 97, 1)
    url         = DMRPFieldStr('url', 98, 124)
    software_id = DMRPFieldStr('software_id', 222, 40)
    package_id  = DMRPFieldStr('package_id', 262, 40)

    def __str__(self) -> str:
        return (f"{self.pkt_type} peer:{self.peer_id} "
                f"callsign:'{self.callsign}' rx_freq:'{self.rx_freq}' "
                f"tx_freq:'{self.tx_freq}' power:'{self.power}' "
                f"cc:'{self.color_code}' lat:'{self.lat}' lon:'{self.lon}' "
                f"height:'{self.height}' location:'{self.location}' "
                f"description:'{self.description}' slots:'{self.slots}' "
                f"url:'{self.url}' software_id:'{self.software_id}' "
                f"package_id:'{self.package_id}'")


class DMRPPacketTalkerAlias(DMRPBasePeerPacket):
    PKT_TYPE = b'DMRA'
    PKT_SIZE = 15

    src_id  = DMRPFieldInt('src_id', 8, 3)
    ta_data = DMRPFieldBytes('ta_data', 11, 4)
    ta_str  = DMRPFieldStr('ta_str', 11, 4)

    def __str__(self) -> str:
        return (f"{self.pkt_type} src:{self.src_id} peer:{self.peer_id} "
                f"ta:{self.ta_data!r} ta_str:{self.ta_str}")


class DMRPPacketData(DMRPBasePeerPacket):
    PKT_TYPE = b'DMRD'
    PKT_SIZE = 55

    CallType = enum.StrEnum('CallType', ['UNIT', 'GROUP'])

    seq       = DMRPFieldInt('seq', 4, 1)
    src_id    = DMRPFieldInt('src_id', 5, 3)
    dst_id    = DMRPFieldInt('dst_id', 8, 3)
    peer_id   = DMRPFieldInt('peer_id', 11, 4)
    stream_id = DMRPFieldInt('stream_id', 16, 4)
    bits      = DMRPFieldInt('bits', 15, 1)
    dmr_data  = DMRPFieldBytes('dmr_data', 20, 33)
    ber       = DMRPFieldInt('ber', 53, 1)
    rssi      = DMRPFieldInt('rssi', 54, 1)

    def set_random_stream_id(self) -> None:
        self.stream_id = int.from_bytes(random.randbytes(4), byteorder="big")

    # slot
    def get_slot(self) -> int:
        if self._data is None:
            return 1
        return 2 if self._data[15] & 0x80 else 1

    def set_slot(self, slot: int) -> None:
        if not (1 <= slot <= 2):
            raise DMRPFieldOutOfRangeException("slot", "1..2")
        if self._data is not None:
            self._data[15] = ((self._data[15] & ~0x80) |
                              (0x80 if slot == 2 else 0))

    slot = property(get_slot, set_slot)

    # call_type
    def get_call_type(self) -> CallType:
        if self._data is None or self._data[15] & 0x40 != 0:
            return self.CallType.UNIT
        return self.CallType.GROUP

    def set_call_type(self, call_type: CallType) -> None:
        if call_type not in self.CallType:
            raise DMRPFieldOutOfRangeException(
                "call_type", '|'.join(ct.value for ct in self.CallType))
        if self._data is not None:
            self._data[15] = (
                (self._data[15] & ~0x40) |
                (0x40 if call_type == self.CallType.UNIT else 0))

    call_type = property(get_call_type, set_call_type)

    # frame_type
    def get_frame_type(self) -> int:
        if self._data is None:
            return 0
        return (self._data[15] & 0x30) >> 4

    def set_frame_type(self, frame_type: int) -> None:
        if not (0 <= frame_type < 1<<2):
            raise DMRPFieldOutOfRangeException("frame_type", "uint2")
        if self._data is not None:
            self._data[15] = (self._data[15] & ~0x30) | (frame_type << 4)

    frame_type = property(get_frame_type, set_frame_type)

    # vseq
    def get_vseq(self) -> int:
        if self._data is None:
            return 0
        return self._data[15] & 0xF

    def set_vseq(self, vseq: int) -> None:
        if not (0 <= vseq < 1<<4):
            raise DMRPFieldOutOfRangeException("vseq", "uint4")
        if self._data is not None:
            self._data[15] = (self._data[15] & ~0xF) | (vseq & 0xF)

    vseq = property(get_vseq, set_vseq)

    # is_voice_term
    @property
    def is_voice_term(self) -> bool:
        return self.frame_type == 0x2 and self.vseq == 0x2

    def __str__(self) -> str:
        return self.format()

    def __format__(self, fmtspec: str) -> str:
        return self.format(fmtspec)

    def format(self, fmtspec: str = '') -> str:
        match fmtspec:
            case 'basic':
                return (f"{self.pkt_type} "
                        f"peer:{self.peer_id} "
                        f"stream:{self.stream_id} "
                        f"{self.call_type.name} TS{self.slot} "
                        f"src:{self.src_id} dst:{self.dst_id} "
                        f"bits:{self.bits:08b}")
            case 'ext':
                return str(self) + f" data:{self.dmr_data.hex()}"

        # default
        return (f"{self.pkt_type} "
                f"peer:{self.peer_id} "
                f"stream:{self.stream_id} "
                f"{self.call_type.name} TS{self.slot} "
                f"src:{self.src_id} dst:{self.dst_id} "
                f"bits:{self.bits:08b} frame_type:{self.frame_type} "
                f"vseq:{self.vseq} seq:{self.seq} "
                f"ber:{self.ber} rssi:{self.rssi} "
                f"vt:{'T' if self.is_voice_term else 'f'}")


class DMRPPacketFactory:
    """
    A factory class responsible for creating instances of DMRP packet classes
    based on packet data. This class supports both predefined packet types
    and user-registered custom packet types.
    """

    __instance: Self|None = None

    @classmethod
    def fd(cls, data: bytes) -> DMRPBasePacket:
        """
        Short singleton version of from_data method
        """
        if cls.__instance is None:
            cls.__instance = cls()
        return cls.__instance.from_data(data)

    def __init__(self) -> None:
        """
        Initializes the packet factory with a list of all packet classes.
        These classes must implement a `detect_by_data` class method to
        determine whether they can handle the given input data.
        """
        self.__pclasses = [
            DMRPPacketMasterNoAck,
            DMRPPacketMasterClose, DMRPPacketRepeaterClose,
            DMRPPacketLogin, DMRPPacketAck, DMRPPacketAuth, DMRPPacketConfig,
            DMRPPacketPing, DMRPPacketPong, DMRPPacketSalt,
            DMRPPacketData, DMRPPacketTalkerAlias,
        ]

    def register_custom_packet(self, cls: Type[DMRPBasePacket]) -> None:
        """
        Registers a custom packet class to the factory.

        Args:
            cls: A class that implements the static method `detect_by_data`.
                 If this method returns True, the class is used to create a packet instance.
        """
        self.__pclasses.append(cls)

    def from_data(self, data: bytes) -> DMRPBasePacket:
        """
        Attempts to create an DMRP packet instance of corresponding packet
        class based on packet data.

        Args:
            data (bytes): The raw data from which to create a packet.

        Returns:
            DMRPBasePacket: An instance of a subclass of DMRPBasePacket that matches the data.

        Raises:
            DMRPUnknownPacketTypeException: If no registered packet class can handle the data.
        """
        for cls in self.__pclasses:
            if cls.detect_by_data(data):
                return cls(data)

        ptypestr = data[0:4].decode(encoding='ascii', errors='ignore')
        raise DMRPUnknownPacketTypeException(f"Unknown packet type {ptypestr}")

