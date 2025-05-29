from __future__ import annotations

import enum

from abc import ABC, abstractmethod
from bitarray import bitarray
from dmr_utils3.bptc import decode_full_lc
from typing import NoReturn

from .base_fields import DMRPFieldInt
from .enums import CallType
from .exceptions import DMRPFieldOutOfRangeException
from .exceptions import DMRPL2BadDataException
from .exceptions import DMRPUnknownLCTypeException
from .factory import AbstractFactory, IFactoryProduced


class DMRPL2Base(ABC):
    """
    Base decoder of DMRD packet payload (layer2, 33 bytes)
    """
    DataTypes = enum.StrEnum('DataTypes', ['FULL_LC', 'VOICE_BURST'])

    def __init__(self, data: bytes) -> None:
        self.set_data(data)

    def set_data(self, data: bytes) -> None:
        if len(data) != 33:
            DMRPL2BadDataException("L2 data must be 33 bytes long")

        self.bitdata: bitarray = bitarray(data, endian='big')

    def get_data(self) -> bytes:
        return self.bitdata.tobytes()

    @abstractmethod
    def get_data_type(self) -> DMRPL2Base.DataTypes: ...


class DMRPL2FullLC(DMRPL2Base):
    def get_data_type(self) -> DMRPL2Base.DataTypes:
        return DMRPL2Base.DataTypes.FULL_LC

    def get_full_lc(self) -> bytes:
        return decode_full_lc(self.bitdata[:98] + self.bitdata[-98:]).tobytes()


class DMRPL2VoiceBurst(DMRPL2Base):
    def get_data_type(self) -> DMRPL2Base.DataTypes:
        return DMRPL2Base.DataTypes.VOICE_BURST

    def get_voice_bits(self) -> tuple[bitarray, bitarray]:
        return (self.bitdata[:108], self.bitdata[-108:])

    def get_emb_lc(self) -> bytes:
        return self.bitdata[116:148].tobytes()


class LCBase(IFactoryProduced, ABC):
    DATA_SIZE: int = 9
    FLCOS: list[int] = []

    flco = DMRPFieldInt('flco', 0, 1)

    def __init__(self, data: bytes|None) -> None:
        if data is None:
            self.create()
        else:
            self.from_data(data)

    def create(self, flco: int|None = None):
        self._data: bytearray = bytearray(b'\x00' * self.DATA_SIZE)
        if flco == None and len(self.FLCOS) > 0:
            self.flco = self.FLCOS[0]

    def from_data(self, data: bytes) -> None:
        if len(data) != self.DATA_SIZE:
            raise DMRPL2BadDataException(
                f"LC data must be {self.DATA_SIZE} bytes long")
        self._data = bytearray(data)

    @classmethod
    def detect_by_data(cls, data: bytes) -> bool:
        return len(data) == cls.DATA_SIZE and data[0] in cls.FLCOS


class LCCall(LCBase):
    FLCOS = [0x00, 0x03]
    CALL_TYPE_FLCO_MAP = { 0x00: CallType.GROUP, 0x03: CallType.UNIT }

    @property
    def call_type(self) -> CallType:
        flco = self._data[0] if len(self._data) > 0 else 0
        if flco not in self.CALL_TYPE_FLCO_MAP:
            return CallType.GROUP
        return self.CALL_TYPE_FLCO_MAP[flco]

    dst_id = DMRPFieldInt('dst_id', 3, 3)
    src_id = DMRPFieldInt('src_id', 6, 3)

    def __str__(self) -> str:
        return (f"LC Call {self.flco} {self.call_type.name} "
                f"dst:{self.dst_id} src:{self.src_id}")


class LCLocation(LCBase):
    FLCOS = [0x08]

    # lat
    @property
    def lat(self) -> float:
        """Decode 24-bit signed latitude integer to decimal degrees."""
        lat_24bit = int.from_bytes(self._data[6:9], byteorder="big")
        if lat_24bit & (1 << 23):  # Check sign bit
            lat_24bit -= (1 << 24)  # Convert from two's complement
        return lat_24bit * (180.0 / (1 << 24))  # Map to range [-90, +90]

    # lon
    @property
    def lon(self) -> float:
        """Decode 25-bit signed longitude integer to decimal degrees."""
        lon_25bit = int.from_bytes(self._data[2:6], byteorder="big")
        lon_25bit &= 0x1FFFFFF
        if lon_25bit & (1 << 24):  # Check sign bit
            lon_25bit -= (1 << 25)  # Convert from two's complement
        return lon_25bit * (360.0 / (1 << 25))  # Map to range [-180, +180]

    def __str__(self) -> str:
        return f"LC GPS {self.flco} {self.lat} {self.lon}"


class LCTalkerAlias(LCBase):
    FLCOS = [0x04, 0x05, 0x06, 0x07]

    class Format(enum.Enum):
        _7BIT   = 0b00
        ISO8    = 0b01
        UTF8    = 0b10
        UTF16BE = 0b11

    # format
    def get_format(self) -> Format|None:
        if self.flco != 0x04:
            return None
        return LCTalkerAlias.Format((self._data[2] & 0xC0) >> 6)

    def set_format(self, format: Format) -> None:
        if self.flco != 0x04:
            self.__format = format
        self._data[2] = (self._data[2] & ~0xC0) | ((format.value << 6) & 0xC0)

    format = property(get_format, set_format)

    # len
    def get_len(self) -> int|None:
        if self.flco != 0x04:
            return None
        return int((self._data[2] & 0x3E) >> 1)

    def set_len(self, len: int) -> None:
        if self.flco != 0x04:
            return
        if not (0 <= len < 1<<5):
            raise DMRPFieldOutOfRangeException("len", "uint5")
        if self._data is not None:
            self._data[2] = (self._data[2] & ~0x3E) | ((len << 1) & 0x3E)

    len = property(get_len, set_len)

    @property
    def ta_data(self) -> bytes:
        if self.flco == 0x04:
            if self.format == LCTalkerAlias.Format._7BIT:
                data = self._data[2:9]
                data[0] &= 1
                return bytes(data)
            return bytes(self._data[3:9])
        return bytes(self._data[2:9])

    def __str__(self) -> str:
        return (f"LC TA {self.flco} fmt:{self.format.name} "
                f"len:{self.len} data:{self.ta_data.hex()}")


class LCFactory(AbstractFactory[LCBase]):
    def __init__(self) -> None:
        """
        Initializes the lc analyzer factory with a list of all lc
        analyzer classes.
        """
        super().__init__([LCCall, LCLocation, LCTalkerAlias])

    def not_found(self, data: bytes) -> NoReturn:
        lctype = data[0:1].hex() if len(data) > 0 else ''
        raise DMRPUnknownLCTypeException(f"Unknown lc type '{lctype}'")
