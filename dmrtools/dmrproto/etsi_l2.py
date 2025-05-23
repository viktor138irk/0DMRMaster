from __future__ import annotations

import enum

from abc import ABC, abstractmethod
from bitarray import bitarray
from dmr_utils3.bptc import decode_full_lc

from .exceptions import DMRPL2BadDataException


class DMRPL2Base(ABC):
    DataTypes = enum.StrEnum('DataTypes', [
        'UNKNOWN', 'FULL_LC', 'VOICE_BURST'
    ])

    def __init__(self, data: bytes) -> None:
        self.set_data(data)

    def set_data(self, data: bytes) -> None:
        if len(data) != 33:
            DMRPL2BadDataException("Data must be 33 bytes long")

        self.bitdata: bitarray = bitarray(data, endian='big')

    def get_data(self) -> bytes:
        return self.bitdata.tobytes()

    @abstractmethod
    def get_data_type(self) -> DMRPL2Base.DataTypes:
        pass


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
