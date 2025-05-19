import logging

from time import time

from .dmrproto import DMRPPacketData
from .peer import Peer


class Call:
    DEAD_TIMEOUT = 5
    CLEAN_TIMEOUT = 60
    CLEAN_LOG_TIMEOUT = 3600 * 6  # 6h

    def __init__(self, call_id: int,
                 src_id: int, dst_id: int, peer_id: int,
                 call_type: DMRPPacketData.CallType) -> None:
        self.call_id: int = call_id
        self.src_id: int = src_id
        self.dst_id: int = dst_id
        self.peer_id: int = peer_id
        self.call_type: DMRPPacketData.CallType = call_type
        self.start_time: float = time()
        self.last_packet_time: float = time()
        self.end_time: float|None = None
        self.packets: int = 0
        self.route_to: set[Peer]|None = None
        logging.info(f"Voice call beg {str(self)}")

    @property
    def dst_hr(self) -> str:
        dst: str = f"{self.dst_id}"
        if self.call_type == DMRPPacketData.CallType.GROUP:
            dst = f"TG-{self.dst_id}"
        return dst

    @property
    def is_ended(self) -> bool:
        return self.end_time is not None

    @property
    def is_dead(self) -> bool:
        return (not self.is_ended and
                not self.check_timeout(self.DEAD_TIMEOUT))

    @property
    def time(self) -> float:
        if self.end_time is None:
            return self.last_packet_time - self.start_time
        return self.end_time - self.start_time

    @property
    def to_be_cleaned(self) -> bool:
        return self.is_ended and not self.check_timeout(self.CLEAN_TIMEOUT)

    @property
    def to_be_cleaned_log(self) -> bool:
        return self.is_ended and not self.check_timeout(self.CLEAN_LOG_TIMEOUT)

    def packet_received(self) -> None:
        self.last_packet_time = time()
        self.packets += 1

    def check_timeout(self, timeout: float) -> bool:
        return time() - self.last_packet_time < timeout

    def end(self, by_timeout: bool = False) -> None:
        self.end_time = self.last_packet_time if by_timeout else time()
        action = "t/o" if by_timeout else "end"
        logging.info(f"Voice call {action} {str(self)}")

    def __str__(self) -> str:
        duration = f"dur:{self.time:.1f}s" if self.is_ended else "running"
        res = (f"id:{self.call_id} {self.src_id}->{self.dst_hr} "
               f"peer:{self.peer_id} {duration}")
        return res

    def __repr__(self) -> str:
        return f"<Call '{self.call_id}'>"


class CallKeeper:
    def __init__(self) -> None:
        self.calls: set[Call] = set()
        self.calls_log: set[Call] = set()

    def maintain(self) -> None:
        # end dead calls
        dead_calls: set[Call] = set(call for call in self.calls
                                    if call.is_dead)

        if len(dead_calls) > 0:
            logging.debug(f"Ending dead calls {dead_calls}")
            for call in dead_calls:
                call.end(by_timeout=True)

        logging.debug(
            "Upkeep calls" +
            ("".join(["\n - " + str(call) for call in self.calls])))

        clean_calls: set[Call] = set(call for call in self.calls
                                     if call.to_be_cleaned)

        if len(clean_calls) > 0:
            logging.debug(f"Removing ended calls {clean_calls}")
            self.calls -= clean_calls

        clean_log: set[Call] = set(call for call in self.calls_log
                                   if call.to_be_cleaned_log)
        self.calls_log -= clean_log

    def by_call_id(self, call_id: int) -> Call|None:
        call_id_map: dict[int, Call] = {call.call_id: call
                                        for call in self.calls}
        return call_id_map[call_id] if call_id in call_id_map else None

    def add(self, call: Call) -> None:
        self.calls.add(call)
        self.calls_log.add(call)
