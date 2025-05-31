import argparse
import asyncio
import logging
import traceback

from dmrtools.udpproxy import AbstractUDPProxy
from dmrtools import DMRPPacketFactory
from dmrtools import hexdump
# from dmrtools.dmrproto import DMRPL2FullLC, DMRPL2VoiceBurst
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


def log_packet(direction, data):
    log_message = (
        f"{direction} | {len(data)} bytes\n"
        f"HD: {data.hex()}\n{hexdump(data)}\n"
        f"{get_packet_details(data)}"
    )
    logging.info(log_message)


class UDPProxyLogger(AbstractUDPProxy):
    def on_forward(self, data: bytes, to_server: bool) -> bytes:
        direction = "OUT=>" if to_server else "<==IN"
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
