from __future__ import annotations

import enum


CallType = enum.StrEnum('CallType', ['UNIT', 'GROUP'])


class VoiceType(enum.Enum):
    NONE    = 0b000000
    HEAD    = 0b100001
    BURST_A = 0b010000
    BURST_B = 0b000001
    BURST_C = 0b000010
    BURST_D = 0b000011
    BURST_E = 0b000100
    BURST_F = 0b000101
    TERM    = 0b100010

    @staticmethod
    def from_value(value: int) -> VoiceType:
        try:
            return VoiceType(value)
        except ValueError:
            return VoiceType.NONE

