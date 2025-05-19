import asyncio
import logging

from typing import Any

from .network import IDatagramReceiver, IDatagramSender


class AsyncDatagramServer(asyncio.DatagramProtocol, IDatagramSender):
    def __init__(self) -> None:
        self.receiver: IDatagramReceiver|None = None
        self.transport: Any|None = None

    def connection_made(self, transport: Any) -> None:
        # bug in linux implementation - _SelectorDatagramTransport is
        # not inherited from DatagramTransport. That's why hasattr is used
        if (hasattr(transport, 'sendto') or
            isinstance(transport, asyncio.DatagramTransport)):
                self.transport = transport
        else:
            logging.error("AsyncDatagramServer.connection_made(): "
                          "Unexpected transport received")

    def set_receiver(self, receiver: IDatagramReceiver):
        self.receiver = receiver

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if self.receiver is not None:
            self.receiver.recv_dg(data, addr)

    def send_dg(self, data: bytes, addr: tuple) -> None:
        if self.transport is not None:
            self.transport.sendto(data, addr)

    # def error_received(self, exc: Exception|None) -> None:
    #     logging.error(f"Client protocol error: {exc}")

    def connection_lost(self, exc: Exception|None) -> None:
        logging.info(f"Client connection closed: {exc}")
        self.transport = None

    def close(self) -> None:
        if self.transport:
            self.transport.close()

