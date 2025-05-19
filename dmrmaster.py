import asyncio
import logging

from argparse import ArgumentParser

from api.dmrapi import start_api
from dmrtools import Dispatcher
from dmrtools.app import App
from dmrtools.asyncnetwork import AsyncDatagramServer
from dmrtools.auth import IPeerAuth


class DMRMaster:
    def __init__(self) -> None:
        self.interface: str = '0.0.0.0'
        self.port: int = 62031
        self.web_interface: str = '0.0.0.0'
        self.web_port: int = 8000
        self.dispatcher: Dispatcher|None = None
        self.dg_server: AsyncDatagramServer|None = None

    def setup(self) -> None:
        ap = ArgumentParser(
            prog="dmrmaster.py",
            description='0DMRMaster Server by Alexander Mokrov (UR6LKW)')

        ap.add_argument('-i', '--interface', type=str,
                        help='Interface to listen on. Defaults to 0.0.0.0.')
        ap.add_argument('-p', '--port', type=int,
                        help='UDP port to listen on. Defaults to 62031.')
        ap.add_argument('--web-interface', type=str,
                        help='Interface to run API on. Defaults to 0.0.0.0.')
        ap.add_argument('--web-port', type=int,
                        help='TCP port to run API on. Defaults to 8000.')
        ap.add_argument('-l', '--log-file', type=str, help='Log filename')
        ap.add_argument('-d', '--ll-debug', action='store_true',
                        help='Log level (INFO/DEBUG)')

        args = ap.parse_args()
        # print(args)

        if args.interface is not None:
            self.interface = args.interface
        if args.port is not None:
            self.port = args.port
        if args.web_interface is not None:
            self.web_interface = args.web_interface
        if args.web_port is not None:
            self.web_port = args.web_port

        log_level = logging.DEBUG if args.ll_debug else logging.INFO
        self.setup_log(log_level, args.log_file)

    def setup_log(self, log_level = logging.DEBUG, log_file = None) -> None:
        handlers = [logging.StreamHandler()]

        if log_file:
            file_handler = logging.FileHandler(log_file)
            handlers.append(file_handler)  # type: ignore[arg-type]

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=handlers
        )

    def set_peer_auth(self, peer_auth: IPeerAuth) -> None:
        if self.dispatcher is None:
            logging.error("Can't set auth: no dispatcher")
            return
        logging.debug(f"Peer auth set to {peer_auth}")
        self.dispatcher.peer_auth = peer_auth

    def register_app(self, app: App) -> None:
        if self.dispatcher is None:
            logging.error("Can't register app: no dispatcher")
            return
        self.dispatcher.app_keeper.register(app)

    def config(self) -> None:
        """
        Local config
        """
        pass

    def run(self) -> None:
        """
        Run, go async and handle KeyboardInterupt
        """
        try:
            asyncio.run(self.__async_run())
        except KeyboardInterrupt:
            logging.info("Interrupted by user (Ctrl+C). Exiting gracefully.")

    async def __async_run(self) -> None:
        await self.__start_udp()

        if not isinstance(self.dg_server, AsyncDatagramServer):
            logging.critical(f"Can't listen on {self.interface}:{self.port}")
            return

        self.dispatcher = Dispatcher(self.dg_server)

        self.config()  # local config for apps

        logging.info(f"Starting API on {self.web_interface}:{self.web_port}")

        try:
            await start_api(self.web_interface, self.web_port, self.dispatcher)
            # await asyncio.Future()  # Run forever
        finally:
            self.stop()

    async def __start_udp(self) -> None:
        logging.info(
            f"Starting server listening on {self.interface}:{self.port}")

        loop = asyncio.get_running_loop()
        transport, self.dg_server = await loop.create_datagram_endpoint(
            lambda: AsyncDatagramServer(),
            local_addr=(self.interface, self.port))

    def stop(self) -> None:
        if self.dispatcher is not None:
            self.dispatcher.shutdown()
            self.dispatcher = None
        if self.dg_server is not None:
            self.dg_server.close()
            self.dg_server = None


def main():
    master = DMRMaster();
    master.setup()
    master.run()


if __name__ == '__main__':
    main()
