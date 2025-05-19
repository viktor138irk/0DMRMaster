import asyncio
import logging
import time

from .app import App, IAppCallInterceptor, AppException
from .call import Call
from .dmrproto import DMRPPacketData


class ParrotApp(App, IAppCallInterceptor):
    """
    Simple parrot application
    """
    def __init__(self, parrot_id: int = 9990, repeat_delay: int = 5,
                 enable_unit: bool = True, enable_group: bool = True) -> None:
        # settings
        self.parrot_id: int = parrot_id
        self.repeat_delay: int = repeat_delay
        self.enable_unit: bool = enable_unit
        self.enable_group: bool = enable_group

        super().__init__()

        # internal state
        self._mycalls: set[int] = set()
        self._records: dict[int, list[DMRPPacketData]] = dict()

    @property
    def name(self) -> str:
        return self.get_name()

    async def repeat(self, packets: list[DMRPPacketData]) -> None:
        if self.dispatcher is None:
            raise AppException(
                "send_packets called before dispatcher had been set")

        if len(packets) == 0:
            logging.debug(f"{self.name}: nothing to repeat, 0 packets in call")
            return

        await asyncio.sleep(self.repeat_delay)

        logging.info(f"{self.name}: repeating call")

        stream_id = packets[0].stream_id
        self._mycalls.add(stream_id)

        start_time = time.monotonic()
        for i, p in enumerate(packets):
            self.dispatcher.inject_packet(p)
            if (delay := start_time + (i + 1) * 0.06 - time.monotonic()) > 0:
                await asyncio.sleep(delay)

        self._mycalls.discard(stream_id)

    def record(self, call: Call, p: DMRPPacketData) -> None:
        if p.src_id == self.parrot_id or p.dst_id != self.parrot_id:
            return

        if (p.call_type == DMRPPacketData.CallType.UNIT
            and not self.enable_unit):
                logging.debug(f"{self.name}: unit calls disabled")
                return

        if (p.call_type == DMRPPacketData.CallType.GROUP
            and not self.enable_group):
                logging.debug(f"{self.name}: group calls disabled")
                return

        if p.stream_id in self._mycalls:
            logging.debug(f"{self.name}: skipping my own call")
            return

        if p.stream_id not in self._records:
            logging.info(f"{self.name}: recording {call.call_id}")
            self._records[p.stream_id] = []

        ans_p = p.copy()

        # invert source and dest for unit call
        if p.call_type == DMRPPacketData.CallType.UNIT:
            ans_p.src_id = self.parrot_id
            ans_p.dst_id = p.src_id

        ans_p.stream_id = p.stream_id + 1

        self._records[p.stream_id].append(ans_p)

        if call.is_ended:
            packets: list[DMRPPacketData] = self._records[p.stream_id]
            asyncio.create_task(self.repeat(packets))
            del self._records[p.stream_id]

    #------------------------------------
    # App implementation
    def get_name(self) -> str:
        return f"Parrot {self.parrot_id}"

    #------------------------------------
    # IAppCallInterceptor implementation
    def process_call_packet(self, call: Call, p: DMRPPacketData) -> None:
        self.record(call, p)
