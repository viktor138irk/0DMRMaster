import asyncio
import logging
import traceback

from time import time

from .app import AppKeeper, IAppDispatcher
from .call import Call, CallKeeper
from .dmrproto import DMRPPacketData, DMRPPacketTalkerAlias
from .dmrproto import DMRPPacketFactory, DMRPBasePacket, DMRPBasePeerPacket
from .network import IDatagramReceiver, IDatagramSender
from .peer import Peer, PeerKeeper
from .peer_controller import IPCDispatcher, PeerController
from .auth import IPeerAuth, DenyAllPeerAuth
from .pphex import hexdump


class Dispatcher(IDatagramReceiver, IAppDispatcher, IPCDispatcher):
    MAINTENANCE_PERIOD = 10

    def __init__(self, sender: IDatagramSender) -> None:
        self.sender: IDatagramSender = sender
        self.peer_auth: IPeerAuth = DenyAllPeerAuth()  # Default policy to deny
        self.peer_keeper: PeerKeeper = PeerKeeper()
        self.call_keeper: CallKeeper = CallKeeper()
        self.app_keeper: AppKeeper = AppKeeper(self)

        sender.set_receiver(self)

        asyncio.create_task(self.maintain_task())

    def maintain(self) -> None:
        self.peer_keeper.maintain()
        self.call_keeper.maintain()

    async def maintain_task(self) -> None:
        logging.debug("Dispatcher: periodic maintenance task scheduled")
        while True:
            await asyncio.sleep(self.MAINTENANCE_PERIOD)
            self.maintain()

    def shutdown(self) -> None:
        logging.info("Dispatcher: shutting down")
        for peer in self.peer_keeper.get_all():
            controller: PeerController = PeerController(peer, self)
            controller.send_close()

    def dispatch_data_packet(self, p: DMRPPacketData, orig_addr: tuple) -> None:
        # logging.debug(f"Dispatching packet from {orig_addr}:\n{p}\n")

        call_id = p.stream_id

        if (call := self.call_keeper.by_call_id(call_id)) is None:
            call = Call(p.stream_id, p.src_id, p.dst_id,
                        p.peer_id, p.call_type)
            self.call_keeper.add(call)

            if call.call_type == DMRPPacketData.CallType.UNIT:
                # get peers location and rout unit call
                peers = self.peer_keeper.get_by_unit(p.dst_id)
                if len(peers) > 0:
                    call.route_to = peers

        call.packet_received(p)

        if p.is_voice_term:
            call.end()

        self.app_keeper.process_call_packet(call, p)

        if isinstance(p, DMRPBasePeerPacket):
            self.distribute_by_peers(p, orig_addr, call.route_to)

    def dispatch_ta_packet(self, p: DMRPPacketTalkerAlias,
                           orig_addr: tuple) -> None:
        self.distribute_by_peers(p, orig_addr)

    def distribute_by_peers(self, p: DMRPBasePeerPacket,
                            orig_addr: tuple,
                            peers: set[Peer]|None = None) -> None:
        sendp = p.copy()

        if peers is None:
            peers = self.peer_keeper.get_active()
        for peer in peers:
            if orig_addr == peer.addr:  # skip myself
                continue
            sendp.peer_id = peer.peer_id
            # logging.debug(f" - sending to {peer.logname}"
            #               f"\n{hexdump(sendp.get_data())}\n{sendp}\n")
            self.sender.send_dg(sendp.get_data(), peer.addr)

    #-------------------------------
    # IDatagramReceiver implementation
    def recv_dg(self, data: bytes, addr: tuple) -> None:
        peer: Peer = self.peer_keeper.get_by_addr(addr)
        p: DMRPBasePacket|None = None

        try:
            p = DMRPPacketFactory.fd(data)
            logging.debug(f"Got packet "
                          f"from {peer.logname} | {len(data)} bytes:\n"
                          f"{hexdump(data)}\n"
                          f"{str(p)}\n")
        except Exception as e:
            logging.error(f"Exception with packet "
                          f"from {peer.logname} | {len(data)} bytes:\n"
                          f"{hexdump(data)}\n"
                          f"{traceback.format_exc()}")
            return

        # process in context of the peer by controller
        controller: PeerController = PeerController(peer, self)
        if not controller.process_packet(p):
            return

        if type(p) is DMRPPacketData:
            self.dispatch_data_packet(p, addr)

        if type(p) is DMRPPacketTalkerAlias:
            self.dispatch_ta_packet(p, addr)

    #-------------------------------
    # IAppDispatcher implementation
    def inject_packet(self, p: DMRPPacketData) -> None:
        logging.debug(f"Injecting packet from app")
        self.dispatch_data_packet(p, (None, None))

    #-------------------------------
    # IPCDispatcher implementation
    def send_dg(self, data: bytes, addr: tuple) -> None:
        self.sender.send_dg(data, addr)

    def get_peer_keeper(self) -> PeerKeeper:
        return self.peer_keeper

    def get_peer_auth(self) -> IPeerAuth:
        return self.peer_auth
