import argparse
import asyncio
import logging
import traceback

from bitarray import bitarray

from dmrtools import DMRPPacketFactory
from dmrtools import hexdump
from dmrtools.dmrproto import DMRPL2FullLC, DMRPL2VoiceBurst
from dmrtools.dmrproto import DMRPPacketData
from dmrtools.dmrproto import EmbLCAssembler, LCFactory


def setup_logger(log_file=None):
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        # level=logging.INFO,
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )


elca: dict[int, EmbLCAssembler] = dict()

def get_packet_details(data):
    try:
        p = DMRPPacketFactory.fd(data)
        if type(p) is DMRPPacketData:
            emblcinfo = ""
            if (full_lc := p.get_full_lc()) is not None:
                lcdec = LCFactory.fd(full_lc)
                emblcinfo = f"FullLC:{hexdump(full_lc)}\n{lcdec}\n"
                return f"{p:l2}\n" + emblcinfo
            if p.stream_id not in elca:
                elca[p.stream_id] = EmbLCAssembler()
            if elca[p.stream_id].process_voicedata(p):
                emblcdata = elca[p.stream_id].decode()
                lcdec = LCFactory.fd(emblcdata)
                emblcinfo = f"EmbLC:{hexdump(emblcdata)}\n{lcdec}\n"
                del elca[p.stream_id]
            if p.is_voice_term:
                del elca[p.stream_id]
            return f"{p:l2}\n" + emblcinfo
        return f"{p}\n"
    except:
        return f"Exception while decoding packet:\n{traceback.format_exc()}"


def log_packet(direction, data, addr):
    log_message = (
        f"{direction} {addr[0]}:{addr[1]} | {len(data)} bytes\n"
        f"HD: {data.hex()}\n{hexdump(data)}\n"
        f"{get_packet_details(data)}"
    )
    logging.info(log_message)


class UDPProxyClientProtocol(asyncio.DatagramProtocol):
    def __init__(self, server_address, loop):
        self.server_address = server_address
        self.loop = loop
        self.transport = None
        self.server_transport = None
        self.client_addr = None

    def connection_made(self, transport):
        self.transport = transport
        logging.info(f"Listening for client datagrams")

    def datagram_received(self, data, addr):
        if not self.client_addr:
            self.client_addr = addr
            logging.info(f"Client connected from {self.client_addr}")

        log_packet("OUT=>", data, self.server_address)

        # Forward to server
        self.server_transport.sendto(data)

    def error_received(self, exc):
        logging.error(f"Client protocol error: {exc}")

    def connection_lost(self, exc):
        logging.info("Client connection closed")

class UDPProxyServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, client_protocol):
        self.client_protocol = client_protocol
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.client_protocol.server_transport = transport
        peername = self.transport.get_extra_info('peername')
        logging.info(f"Connected to server {peername}")

    def datagram_received(self, data, addr):
        if self.client_protocol.client_addr:
            log_packet("<==IN", data, self.client_protocol.client_addr)

            # Send data to client
            self.client_protocol.transport.sendto(
                data, self.client_protocol.client_addr)

    def error_received(self, exc):
        logging.error(f"Server protocol error: {exc}")

    def connection_lost(self, exc):
        logging.info("Server connection closed")


async def start_udp_proxy(listen_ip, listen_port, server_ip, server_port):
    loop = asyncio.get_running_loop()

    server_address = (server_ip, server_port)

    # Create client listener
    listen = await loop.create_datagram_endpoint(
        lambda: UDPProxyClientProtocol(server_address, loop),
        local_addr=(listen_ip, listen_port)
    )
    client_transport, client_protocol = listen

    # Connect to server
    connect = await loop.create_datagram_endpoint(
        lambda: UDPProxyServerProtocol(client_protocol),
        remote_addr=server_address
    )
    server_transport, server_protocol = connect

    logging.info(f"Proxy running: {listen_ip}:{listen_port} <=> {server_ip}:{server_port}")

    try:
        await asyncio.Future()  # Run forever
    finally:
        client_transport.close()
        server_transport.close()


def parse_arguments():
    parser = argparse.ArgumentParser(description='Simple UDP Proxy with Hex Logging (Asyncio Version)')
    parser.add_argument('listenip', type=str, help='IP address to listen on')
    parser.add_argument('listenport', type=int, help='Port to listen on')
    parser.add_argument('serverip', type=str, help='Server IP address to forward to')
    parser.add_argument('serverport', type=int, help='Server port to forward to')
    parser.add_argument('-l', '--log-file', type=str, help='Log filename')
    return parser.parse_args()


def main():
    args = parse_arguments()
    setup_logger(args.log_file)

    try:
        asyncio.run(start_udp_proxy(args.listenip, args.listenport,
                                    args.serverip, args.serverport))
    except KeyboardInterrupt:
        logging.info("Shutting down.")


if __name__ == "__main__":
    main()
