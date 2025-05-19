import logging

from abc import ABC, abstractmethod

from .auth import IPeerAuth
from .dmrproto import DMRPBasePacket
from .dmrproto import DMRPPacketConfig, DMRPPacketPing, DMRPPacketPong
from .dmrproto import DMRPPacketData, DMRPPacketTalkerAlias
from .dmrproto import DMRPPacketLogin, DMRPPacketSalt, DMRPPacketAuth
from .dmrproto import DMRPPacketMasterClose, DMRPPacketRepeaterClose
from .dmrproto import DMRPPacketMasterNoAck, DMRPPacketAck
from .peer import Peer, PeerKeeper
from .pphex import hexdump


class IPCDispatcher(ABC):
    """
    Dispatcher interface to pass into controller to call back
    """
    @abstractmethod
    def send_dg(self, data: bytes, addr: tuple) -> None:
        pass

    @abstractmethod
    def get_peer_keeper(self) -> PeerKeeper:
        pass

    @abstractmethod
    def get_peer_auth(self) -> IPeerAuth:
        pass


class PeerController:
    def __init__(self, peer: Peer, dispatcher: IPCDispatcher) -> None:
        self.peer: Peer = peer
        self.dispatcher: IPCDispatcher = dispatcher
        self.peer_auth: IPeerAuth = dispatcher.get_peer_auth()

    def process_packet(self, p: DMRPBasePacket) -> bool:
        """
        Process packet in context of the peer

        Returns:
            True - continue processing with dispatcher (for data)
            False - stop processing (peer cmds)
        """
        # CLOSE packet
        if type(p) is DMRPPacketRepeaterClose:
            logging.info(f"Peer {self.peer.logname} disconnected")
            self.peer.die()
            return False

        # DATA packet
        if type(p) is DMRPPacketData:
            if not self.peer.status.is_applicable(Peer.Status.ACTIVE):
                logging.debug(
                    f"Got DMRPPacketData "
                    f"while status is {self.peer.status.name}")
                logging.error(f"Data from inactive peer {self.peer.logname}. "
                              f"Closing connection.")
                self.peer.die()
                self.send_close(p.peer_id)
                return False

            self.peer.update_active()
            self.peer.update_unit(p.src_id)
            return True

        # PING packet
        if type(p) is DMRPPacketPing:
            if not self.peer.status.is_applicable(Peer.Status.ACTIVE):
                logging.debug(
                    f"Got DMRPPacketPing "
                    f"while status is {self.peer.status.name}")
                logging.error(f"Ping from inactive peer {self.peer.logname}. "
                              f"Closing connection.")
                self.peer.die()
                self.send_close(p.peer_id)
                return False

            logging.debug(f"Ping-pong {self.peer.logname}.")
            self.peer.update_active()
            self.send_pong()
            return False

        # LOGIN sequence
        if type(p) is DMRPPacketLogin:
            if not self.peer.status.is_applicable(Peer.Status.LOGIN):
                logging.debug(
                    f"Got DMRPPacketLogin "
                    f"while status is {self.peer.status.name}")
                logging.error(f"Bad login sequence from {self.peer.logname}. "
                              f"Closing connection.")
                self.peer.die()
                self.send_close(p.peer_id)
                return False

            peer_keeper: PeerKeeper = self.dispatcher.get_peer_keeper()
            if len(peer_keeper.get_by_id(p.peer_id)) > 0:
                logging.error(f"Auth {self.peer.logname}: "
                              f"peer id {p.peer_id} is already connected")
                self.peer.die()
                self.send_close(p.peer_id)
                return False

            if not self.peer_auth.allow_peer_id(p.peer_id):
                logging.error(f"Auth {self.peer.logname}: "
                              f"peer id {p.peer_id} disabled")
                self.peer.die()
                self.send_close(p.peer_id)
                return False

            self.peer.status = Peer.Status.AUTH
            logging.info(f"Login request from {self.peer.logname}"
                         f" ({p.peer_id})")
            self.send_salt()
            return False

        if type(p) is DMRPPacketAuth:
            if not self.peer.status.is_applicable(Peer.Status.AUTH):
                logging.debug(
                    f"Got DMRPPacketAuth "
                    f"while status is {self.peer.status.name}")
                logging.error(f"Bad login sequence from {self.peer.logname}. "
                              f"Closing connection.")
                self.peer.die()
                self.send_close(p.peer_id)
                return False

            if (self.peer.auth_salt is None or
                not self.peer_auth.check_password(p.peer_id,
                                                  self.peer.auth_salt,
                                                  p.pass_hash)):
                    logging.error(
                        f"Auth {self.peer.logname}: password incorrect")
                    self.peer.die()
                    self.send_close(p.peer_id)
                    return False

            self.peer.peer_id = p.peer_id
            self.peer.status = Peer.Status.CONFIG
            logging.info(f"Auth success {self.peer.logname}")
            self.send_ack_ok()
            return False

        if type(p) is DMRPPacketConfig:
            if not self.peer.status.is_applicable(Peer.Status.CONFIG):
                logging.debug(
                    f"Got DMRPPacketConfig "
                    f"while status is {self.peer.status.name}")
                logging.error(f"Bad login sequence from {self.peer.logname}. "
                              f"Closing connection.")
                self.peer.die()
                self.send_close(p.peer_id)
                return False

            config = {
                'callsign': p.callsign,
                'rx_freq': p.rx_freq,
                'tx_freq': p.tx_freq,
                'power': p.power,
                'color_code': p.color_code,
                'lat': p.lat,
                'lon': p.lon,
                'height': p.height,
                'location': p.location,
                'description': p.description,
                'slots': p.slots,
                'url': p.url,
                'software_id': p.software_id,
                'package_id': p.package_id,
            }
            logging.info(f"Config from {self.peer.logname}: " +
                         ", ".join(f"{k}={v}" for k, v in config.items()));

            self.peer.status = Peer.Status.ACTIVE
            self.peer.config = config
            self.send_ack_ok()
            return False

        return True

    def send_data(self, p: DMRPBasePacket) -> None:
        data: bytes = p.get_data()
        logging.debug(
            f"Sending packet to {self.peer.logname} | {len(data)} bytes:\n"
            f"{hexdump(data)}\n"
            f"{str(p)}\n")
        self.dispatcher.send_dg(p.get_data(), self.peer.addr)

    def send_close(self, peer_id: int = 0) -> None:
        p = DMRPPacketMasterClose()
        p.peer_id = peer_id if peer_id != 0 else self.peer.peer_id
        self.send_data(p)

    def send_salt(self) -> None:
        p = DMRPPacketSalt()
        p.set_random_salt()
        self.peer.auth_salt = p.salt
        self.send_data(p)

    def send_ack_ok(self) -> None:
        p = DMRPPacketAck()
        p.peer_id = self.peer.peer_id
        self.send_data(p)

    def send_pong(self) -> None:
        p = DMRPPacketPong()
        p.peer_id = self.peer.peer_id
        self.send_data(p)
