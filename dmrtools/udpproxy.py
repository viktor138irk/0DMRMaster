from __future__ import annotations

import asyncio
import logging

from abc import ABC, abstractmethod


class AbstractUDPProxy(ABC):
    def __init__(self, server_host: str, server_port: int,
                 listen_host: str, listen_port: int) -> None:
        self.listen_host: str = listen_host
        self.listen_port: int = listen_port
        self.server_host: str = server_host
        self.server_port: int = server_port

        self.transport_client: asyncio.DatagramTransport|None = None
        self.transport_server: asyncio.DatagramTransport|None = None

        self.client_address: tuple|None = None

    def on_forward(self, data: bytes, to_server: bool) -> bytes:
        """
        Intercept or modify packet data before forwarding.
        to_server: True means direction from client to server, False otherwise
        """
        return data

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        # Start the listening endpoint for the client
        self.transport_client, _ = await loop.create_datagram_endpoint(
            lambda: self.ClientProtocol(self),
            local_addr=(self.listen_host, self.listen_port)
        )

        logging.info(
            f"Listening for on {self.listen_host}:{self.listen_port}")

    def reset(self) -> None:
        if self.transport_client:
            self.transport_client.close()
        self.transport_client = None

        if self.transport_server:
            self.transport_server.close()
        self.transport_server = None

        self.client_address = None

        logging.debug("Proxy reset to LISTENING state")

    async def connect_to_dest(self):
        loop = asyncio.get_running_loop()

        self.transport_server, _ = await loop.create_datagram_endpoint(
            lambda: self.ServerProtocol(self),
            remote_addr=(self.server_host, self.server_port)
        )

        logging.info("Proxying "
              f"{self.client_address[0]}:{self.client_address[1]}"
              f" <=> {self.server_host}:{self.server_port}")

    class ClientProtocol(asyncio.DatagramProtocol):
        def __init__(self, proxy: AbstractUDPProxy) -> None:
            self.proxy: AbstractUDPProxy = proxy

        def datagram_received(self, data: bytes, addr: tuple) -> None:
            if self.proxy.client_address is None:
                self.proxy.client_address = addr
                logging.info(f"Client {addr[0]}:{addr[1]} connected")
                asyncio.create_task(self.proxy.connect_to_dest())

            if addr != self.proxy.client_address:
                logging.error("Ignoring packet from unknown client"
                      f" {addr[0]}:{addr[1]}")
                return

            if self.proxy.transport_server:
                try:
                    data = self.proxy.on_forward(data, to_server=True)
                    self.proxy.transport_server.sendto(data)
                except Exception as e:
                    logging.error(f"Error forwarding to server: {e}")
                    self.proxy.reset()

        def error_received(self, exc: Exception|None) -> None:
            logging.error(f"Client socket error: {exc}")
            self.proxy.reset()

        def connection_lost(self, exc: Exception|None) -> None:
            logging.error(f"Client connection lost: {exc}")
            self.proxy.reset()

    class ServerProtocol(asyncio.DatagramProtocol):
        def __init__(self, proxy: AbstractUDPProxy) -> None:
            self.proxy: AbstractUDPProxy = proxy

        def datagram_received(self, data: bytes, addr: tuple) -> None:
            if self.proxy.transport_client and self.proxy.client_address:
                try:
                    data = self.proxy.on_forward(data, to_server=False)
                    self.proxy.transport_client.sendto(
                        data, self.proxy.client_address)
                except Exception as e:
                    logging.error(f"Error forwarding to client: {e}")
                    self.proxy.reset()

        def error_received(self, exc: Exception|None) -> None:
            logging.error(f"Server socket error: {exc}")
            self.proxy.reset()

        def connection_lost(self, exc: Exception|None) -> None:
            logging.error(f"Server connection lost: {exc}")
            self.proxy.reset()
