import logging

from bitarray import bitarray
from dmr_utils3.bptc import decode_emblc

from .enums import CallType, VoiceType
from .etsi_l2 import DMRPL2FullLC, DMRPL2VoiceBurst
from .etsi_l2 import LCFactory, LCBase
from .etsi_l2 import LCLocation, LCCall, LCTalkerAlias
from .exceptions import CallLCDecoderException, EmbLCAssemblerException
from .mmdvm_l1 import DMRPPacketData


class EmbLCAssembler:
    """
    This is auxiliary class to assemble a few voice packets and
    assemble embedded LC from them.

    How to use: pass DMRD packets from the same stream id to process_voicedata, if it returns true, then embedded LC can be decoded with decode()
    """
    VTYPE_N_MAP: dict[VoiceType, int] = {
        VoiceType.BURST_B: 0,
        VoiceType.BURST_C: 1,
        VoiceType.BURST_D: 2,
        VoiceType.BURST_E: 3
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.lcs: list[bytes] = []
        self.vseq: int = 0

    def process_voicedata(self, p: DMRPPacketData) -> bool:
        if p.voice_type not in EmbLCAssembler.VTYPE_N_MAP:
            return False

        burst_n = EmbLCAssembler.VTYPE_N_MAP[p.voice_type]

        # check voice sequence for next packets
        if burst_n > 0 and p.vseq != (self.vseq + 1) & 0xFF:
            err_msg = f"Wrong vseq ({p.vseq}, expected {self.vseq + 1})"
            self.reset()
            raise EmbLCAssemblerException(err_msg)

        # check, if burst sequence matches collected
        if len(self.lcs) != burst_n:
            err_msg = f"Wrong burst N ({burst_n}, expected {len(self.lcs)})"
            self.reset()
            raise EmbLCAssemblerException(err_msg)

        # try getting LC and collect
        emblc = p.get_emb_lc()
        if emblc is None:
            self.reset()
            raise EmbLCAssemblerException("Can't get data")

        self.lcs.append(emblc)
        self.vseq = p.vseq

        return burst_n == 3

    def decode(self) -> bytes|None:
        if len(self.lcs) != 4:
            return None

        emblc_data: bitarray = bitarray(b"".join(self.lcs), endian='big')
        return decode_emblc(emblc_data)


class CallLCDecoder:
    """
    Decode and collect both full lc and embedded lc in the same call
    """
    def __init__(self, stream_id: int) -> None:
        self.stream_id: int = stream_id
        self.lcs: dict[int, LCBase] = {}  # flco -> child(LCBase)
        self._assembler: EmbLCAssembler = EmbLCAssembler()

    def process_voicedata(self, p: DMRPPacketData) -> LCBase|None:
        if p.stream_id != self.stream_id:
            raise CallLCDecoderException("Wrong stream_id")

        if (full_lc := p.get_full_lc()) is not None:
            return self._add_lc(full_lc)
        else:
            try:
                if (self._assembler.process_voicedata(p)
                    and (lc_data := self._assembler.decode()) is not None):
                        self._assembler.reset()
                        return self._add_lc(lc_data)
            except Exception as e:
                logging.debug(f"Exception while processing lc data: {e}")
        return None

    def _add_lc(self, lc_data: bytes) -> LCBase:
        lc = LCFactory.fd(lc_data)
        self.lcs[lc.flco] = lc
        return lc

    @property
    def call(self) -> LCCall|None:
        for flco in LCCall.FLCOS:
            if (flco in self.lcs and
                type(lc := self.lcs[flco]) is LCCall):
                    return lc
        return None

    @property
    def location(self) -> LCLocation|None:
        if (LCLocation.FLCOS[0] in self.lcs and
            type(lc := self.lcs[LCLocation.FLCOS[0]]) is LCLocation):
                return lc
        return None

    @property
    def ta(self) -> str|None:
        return self.get_ta()

    def get_ta(self, partial: bool = False) -> str|None:
        # check if first part of TA part collected
        if LCTalkerAlias.FLCOS[0] not in self.lcs:
            return None

        lcta0 = self.lcs[LCTalkerAlias.FLCOS[0]]
        if type(lcta0) is not LCTalkerAlias:
            return None

        # collect all datas
        ta_data: bytes = b""
        for flco in LCTalkerAlias.FLCOS:
            if flco in self.lcs and type(lc := self.lcs[flco]) is LCTalkerAlias:
                ta_data += lc.ta_data

        ta_len = lcta0.len
        encoding = "utf-8"

        match lcta0.format:
            case LCTalkerAlias.Format._7BIT:
                return None  # Not supported; !!TODO: decode 7-bit
            case LCTalkerAlias.Format.ISO8:
                encoding = "iso-8859-1"
            case LCTalkerAlias.Format.UTF8:
                encoding = "utf-8"
            case LCTalkerAlias.Format.UTF16BE:
                encoding = "utf-16-be"

        ta_str = ta_data.decode(encoding=encoding, errors='replace')
        if len(ta_str) < ta_len:  # not collected all TA LCs yet
            return ta_str if partial else None

        return ta_str[:ta_len]
