from __future__ import annotations

import asyncio
import logging

from typing import Optional


class UDPProxy:
    def __init__(self, server_host: str, server_port: int,
                 listen_host: str, listen_port: int) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.server_host = server_host
        self.server_port = server_port

        self.listener_transport: asyncio.DatagramTransport|None = None
        self.sessions: dict[tuple[str, int], UDPProxy.Session] = {}

    def on_forward(self, data: bytes, to_server: bool,
                   client_addr: tuple[str, int]) -> bytes:
        """
        Intercept or modify packet data before forwarding.
        to_server: True means direction from client to server, False otherwise
        """
        return data

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        self.listener_transport, _ = await loop.create_datagram_endpoint(
            lambda: self.ListenerProtocol(self),
            local_addr=(self.listen_host, self.listen_port)
        )

        logging.info(f"Listening for clients on {self.listen_host}:{self.listen_port}")

    async def _create_session(self, client_addr: tuple[str, int]) -> Session:
        loop = asyncio.get_running_loop()

        transport, _ = await loop.create_datagram_endpoint(
            lambda: self.ServerProtocol(self, client_addr),
            remote_addr=(self.server_host, self.server_port)
        )

        session = UDPProxy.Session(proxy=self,
                                           client_addr=client_addr,
                                           server_transport=transport)

        self.sessions[client_addr] = session

        logging.info(f"Proxying {client_addr[0]}:{client_addr[1]}"
                     f" <=> {self.server_host}:{self.server_port}")

        return session

    def remove_session(self, client_addr: tuple[str, int]) -> None:
        session = self.sessions.pop(client_addr, None)
        if session:
            session.server_transport.close()
            logging.info(f"Closed session for {client_addr}")

    class Session:
        def __init__(self, proxy: UDPProxy, client_addr: tuple[str, int],
                     server_transport: asyncio.DatagramTransport) -> None:
            self.proxy = proxy
            self.client_addr = client_addr
            self.server_transport = server_transport

        def handle_from_client(self, data: bytes) -> None:
            try:
                data = self.proxy.on_forward(data, to_server=True,
                                             client_addr=self.client_addr)

                self.server_transport.sendto(data)
            except Exception as e:
                logging.error(
                    "Error forwarding to server for "
                    f"{self.client_addr[0]}:{self.client_addr[1]}: {e}")
                self.proxy.remove_session(self.client_addr)

        def handle_from_server(self, data: bytes) -> None:
            try:
                data = self.proxy.on_forward(data, to_server=False,
                                             client_addr=self.client_addr)
                if self.proxy.listener_transport:
                    self.proxy.listener_transport.sendto(data, self.client_addr)
            except Exception as e:
                logging.error(
                    "Error forwarding to client "
                    f"{self.client_addr[0]}:{self.client_addr[1]}: {e}")
                self.proxy.remove_session(self.client_addr)

    class ListenerProtocol(asyncio.DatagramProtocol):
        def __init__(self, proxy: UDPProxy) -> None:
            self.proxy = proxy

        def datagram_received(self, data: bytes,
                              addr: tuple[str, int]) -> None:
            session = self.proxy.sessions.get(addr)
            if not session:
                asyncio.create_task(self._handle_new_client(data, addr))
                return
            session.handle_from_client(data)

        async def _handle_new_client(self, data: bytes,
                                     addr: tuple[str, int]) -> None:
            session = await self.proxy._create_session(addr)
            session.handle_from_client(data)

        def error_received(self, exc: Exception) -> None:
            logging.error(f"Listener socket error: {exc}")

    class ServerProtocol(asyncio.DatagramProtocol):
        def __init__(self, proxy: UDPProxy,
                     client_addr: tuple[str, int]) -> None:
            self.proxy = proxy
            self.client_addr = client_addr

        def datagram_received(self, data: bytes,
                              addr: tuple[str, int]) -> None:
            session = self.proxy.sessions.get(self.client_addr)
            if session:
                session.handle_from_server(data)

        def error_received(self, exc: Exception) -> None:
            logging.error("Server socket error for "
                          f"{self.client_addr[0]}:{self.client_addr[1]}: {exc}")
            self.proxy.remove_session(self.client_addr)

        def connection_lost(self, exc: Exception | None) -> None:
            logging.error("Server connection lost for "
                          f"{self.client_addr[0]}:{self.client_addr[1]}: {exc}")
            self.proxy.remove_session(self.client_addr)
