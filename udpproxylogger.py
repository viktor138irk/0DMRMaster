import argparse
import asyncio
import logging
import traceback

from dmrtools.udpproxy import UDPProxy
from dmrtools import DMRPPacketFactory
from dmrtools import hexdump
from dmrtools.dmrproto import DMRPPacketData
from dmrtools.dmrproto import CallLCDecoder, LCFactory, LCTalkerAlias


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


lcd: dict[int, CallLCDecoder] = dict()

def get_packet_details(data):
    try:
        p = DMRPPacketFactory.fd(data)
        if type(p) is DMRPPacketData:
            if p.stream_id not in lcd:
                lcd[p.stream_id] = CallLCDecoder(p.stream_id)
            if (lc := lcd[p.stream_id].process_voicedata(p)) is not None:
                if type(lc) is LCTalkerAlias:
                    if (ta := lcd[p.stream_id].ta) is not None:
                        return f"{p:l2}\nLCdata: {hexdump(lc._data)}\n{lc}\nTA: {ta}\n"
                return f"{p:l2}\nLCdata: {hexdump(lc._data)}\n{lc}\n"
            return f"{p:l2}\n"
        return f"{p}\n"
    except:
        return f"Exception while decoding packet:\n{traceback.format_exc()}"


def log_packet(direction, data):
    log_message = (
        f"{direction} | {len(data)} bytes\n"
        f"HD: {data.hex()}\n{hexdump(data)}\n"
        f"{get_packet_details(data)}"
    )
    logging.info(log_message)


class UDPProxyLogger(UDPProxy):
    def on_forward(self, data: bytes, to_server: bool,
                   client_addr: tuple[str, int]) -> bytes:
        ca_str = f"{client_addr[0]}:{client_addr[1]}"
        direction = f"{ca_str} =>" if to_server else f"{ca_str} <="
        log_packet(direction, data)
        return data


async def start_udp_proxy(server_ip, server_port, listen_ip, listen_port):
    logging.info(f"Proxy running: {listen_ip}:{listen_port} <=> {server_ip}:{server_port}")

    proxy = UDPProxyLogger(server_ip, server_port, listen_ip, listen_port)
    await proxy.start()

    try:
        await asyncio.Future()  # Run forever
    finally:
        # await proxy.stop()
        pass


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
        asyncio.run(start_udp_proxy(args.serverip, args.serverport,
                                    args.listenip, args.listenport))
    except KeyboardInterrupt:
        logging.info("Shutting down.")


if __name__ == "__main__":
    main()
