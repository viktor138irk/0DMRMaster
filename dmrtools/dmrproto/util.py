import logging

from bitarray import bitarray
from dmr_utils3.bptc import decode_emblc

from .mmdvm_l1 import DMRPPacketData


class EmbLCAssembler:
    """
    This is auxiliary class to assemble a few voice packets and
    assemble embedded LC from them.

    How to use: pass DMRD packets from the same stream id to process_voicedata, if it returns true, then embedded LC can be decoded with decode()
    """
    VTYPE_N_MAP: dict[DMRPPacketData.VoiceType, int] = {
        DMRPPacketData.VoiceType.BURST_B: 0,
        DMRPPacketData.VoiceType.BURST_C: 1,
        DMRPPacketData.VoiceType.BURST_D: 2,
        DMRPPacketData.VoiceType.BURST_E: 3
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.lcs: list[bytes] = list()
        self.vseq: int = 0

    def process_voicedata(self, p: DMRPPacketData) -> bool:
        if p.voice_type not in EmbLCAssembler.VTYPE_N_MAP:
            return False

        burst_n = EmbLCAssembler.VTYPE_N_MAP[p.voice_type]

        # check voice sequence for next packets
        if burst_n > 0 and p.vseq != (self.vseq + 1) % 0x100:
            logging.error("Embedded LC failed: wrong vseq "
                          f"({p.vseq}, expected {self.vseq + 1})")
            self.reset()
            return False

        # check, if burst sequence matches collected
        if len(self.lcs) != burst_n:
            logging.error("Embedded LC failed: wrong burst N "
                          f"({burst_n}, expected {len(self.lcs)})")
            self.reset()
            return False

        # try getting LC and collect
        emblc = p.get_emb_lc()
        if emblc is None:
            logging.error("Embedded LC failed: can't get")
            self.reset()
            return False

        self.lcs.append(emblc)
        self.vseq = p.vseq

        # logging.debug(f"assembled emblc's: {self.lcs}")

        return burst_n == 3

    def decode(self) -> bytes|None:
        if len(self.lcs) != 4:
            return None

        emblc_data: bitarray = bitarray(b"".join(self.lcs), endian='big')
        return decode_emblc(emblc_data)
