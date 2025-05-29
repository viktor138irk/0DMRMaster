from __future__ import annotations

import random

from abc import ABC
from hashlib import sha256
from typing import Self, TypeAlias, NoReturn

from .base_fields import DMRPFieldInt, DMRPFieldBytes, DMRPFieldStr
from .enums import CallType, VoiceType
from .etsi_l2 import DMRPL2Base, DMRPL2FullLC, DMRPL2VoiceBurst
from .exceptions import DMRPBadPacketException
from .exceptions import DMRPFieldOutOfRangeException
from .exceptions import DMRPUnknownPacketTypeException
from .factory import AbstractFactory, IFactoryProduced


#############################
# Functions
#############################
def calc_password_hash(salt: bytes, password: str) -> bytes:
    return sha256(salt + password.encode()).digest()


#############################
# Packet classes hierarchy
#############################
class DMRPBasePacket(IFactoryProduced, ABC):
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
            DMRPBadPacketException: if size or type doesn't match
        """
        self._data = None
        if not data.startswith(self.PKT_TYPE):
            raise DMRPBadPacketException(
                f"Bad packet type: '{data[0:4]!r}', expected '{self.PKT_TYPE!r}'")
        if len(data) != self.PKT_SIZE:
            raise DMRPBadPacketException(
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
    class DMRPFieldPeerAuto(DMRPFieldInt):
        """
        Int field, which autodetects header length (PKT_TYPE) and
        offsets peer_id for its len
        """
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


class DMRPPacketBeacon(DMRPBasePeerPacket):
    PKT_TYPE = b'RPTSBKN'
    PKT_SIZE = 11


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

    CallType: TypeAlias = CallType  # legacy alias
    VoiceType: TypeAlias = VoiceType  # legacy alias

    """
    bits:
    | 7    | 6         | 5    4     | 3 2 1 0 |
    | slot | call_type | frame_type | vseq    |
    |                  |      voice_type      |
    """

    seq       = DMRPFieldInt('seq', 4, 1)
    src_id    = DMRPFieldInt('src_id', 5, 3)
    dst_id    = DMRPFieldInt('dst_id', 8, 3)
    peer_id   = DMRPFieldInt('peer_id', 11, 4)
    stream_id = DMRPFieldInt('stream_id', 16, 4)
    bits      = DMRPFieldInt('bits', 15, 1)
    dmr_data  = DMRPFieldBytes('dmr_data', 20, 33)
    ber       = DMRPFieldInt('ber', 53, 1)
    rssi      = DMRPFieldInt('rssi', 54, 1)

    def __init__(self, data: bytes|None = None) -> None:
        self.__l2: DMRPL2Base|None = None
        super().__init__(data)

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
            return CallType.UNIT
        return CallType.GROUP

    def set_call_type(self, call_type: CallType) -> None:
        if call_type not in CallType:
            raise DMRPFieldOutOfRangeException(
                "call_type", '|'.join(ct.value for ct in CallType))
        if self._data is not None:
            self._data[15] = (
                (self._data[15] & ~0x40) |
                (0x40 if call_type == CallType.UNIT else 0))

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

    # voice_type
    def get_voice_type(self) -> VoiceType:
        return VoiceType.from_value(self.bits & 0x3F)

    def set_voice_type(self, voice_type: VoiceType) -> None:
        if self._data is not None:
            self._data[15] = ((self._data[15] & ~0x3F) |
                              (voice_type.value & 0x3F))

    voice_type = property(get_voice_type, set_voice_type)

    # is_voice_term
    @property
    def is_voice_term(self) -> bool:
        return self.voice_type == VoiceType.TERM

    def get_l2(self) -> DMRPL2Base|None:
        if self.__l2 is not None:
            return self.__l2

        if self.voice_type in (VoiceType.HEAD,
                               VoiceType.TERM):
            self.__l2 = DMRPL2FullLC(self.dmr_data)

        if self.voice_type in (VoiceType.BURST_A,
                               VoiceType.BURST_B,
                               VoiceType.BURST_C,
                               VoiceType.BURST_D,
                               VoiceType.BURST_E,
                               VoiceType.BURST_F):
            self.__l2 = DMRPL2VoiceBurst(self.dmr_data)

        return self.__l2

    def get_full_lc(self) -> bytes|None:
        l2 = self.get_l2()
        if type(l2) is DMRPL2FullLC:
            return l2.get_full_lc()
        return None

    def get_emb_lc(self) -> bytes|None:
        l2 = self.get_l2()
        if type(l2) is DMRPL2VoiceBurst:
            return l2.get_emb_lc()
        return None

    def get_lc(self) -> bytes:
        if ((lcdata := self.get_full_lc()) is not None or
            (lcdata := self.get_emb_lc()) is not None):
                return lcdata
        return b""

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
                return (self.format('') +
                        f" data:{self.dmr_data.hex()}")

            case 'l2':
                return (self.format('') +
                        f" lc:{self.get_lc().hex()}" +
                        f" data:{self.dmr_data.hex()}")

        # default
        return (f"{self.pkt_type} "
                f"peer:{self.peer_id} "
                f"stream:{self.stream_id} "
                f"{self.call_type.name} TS{self.slot} "
                f"src:{self.src_id} dst:{self.dst_id} "
                f"bits:{self.bits:08b} "
                f"frame_type:{self.frame_type} vseq:{self.vseq} "
                f"voice_type:{self.voice_type.name} seq:{self.seq} "
                f"ber:{self.ber} rssi:{self.rssi} "
                f"vt:{'T' if self.is_voice_term else 'f'}")


class DMRPPacketFactory(AbstractFactory[DMRPBasePacket]):
    """
    A factory class responsible for creating instances of DMRP packet classes
    based on packet data. This class supports both predefined packet types
    and user-registered custom packet types.
    """

    def __init__(self) -> None:
        """
        Initializes the packet factory with a list of all packet classes.
        """
        super().__init__([
            DMRPPacketMasterNoAck,
            DMRPPacketMasterClose, DMRPPacketRepeaterClose,
            DMRPPacketLogin, DMRPPacketAck, DMRPPacketAuth, DMRPPacketConfig,
            DMRPPacketPing, DMRPPacketPong, DMRPPacketSalt, DMRPPacketBeacon,
            DMRPPacketData, DMRPPacketTalkerAlias,
        ])

    def not_found(self, data: bytes) -> NoReturn:
        ptypestr = data[0:4].decode(encoding='ascii', errors='ignore')
        raise DMRPUnknownPacketTypeException(f"Unknown packet type {ptypestr}")

