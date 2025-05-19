from __future__ import annotations

import enum
import logging

from time import time


class Unit:
    TIMEOUT = 3600

    def __init__(self, unit_id: int) -> None:
        self.unit_id: int = unit_id
        self.active_time: float = time()

    def update_active(self) -> None:
        self.active_time = time()

    def check_timeout(self) -> bool:
        return time() - self.active_time < self.TIMEOUT


class Peer:
    class Status(enum.IntEnum):
        LOGIN  = enum.auto()
        AUTH   = enum.auto()
        CONFIG = enum.auto()
        ACTIVE = enum.auto()
        DEAD   = enum.auto()

        def is_applicable(self, test_status: Peer.Status) -> bool:
            """
            Loose check, if test_status is applicable for the current one,
            like we can treat any status except DEAD as LOGIN and accept login
            packet in it
            """
            applicable_map: dict[Peer.Status, set[Peer.Status]] = {
                # current status --> Applicable test statuses
                Peer.Status.AUTH:   {Peer.Status.LOGIN,
                                     Peer.Status.AUTH},
                Peer.Status.CONFIG: {Peer.Status.LOGIN,
                                     Peer.Status.AUTH,
                                     Peer.Status.CONFIG},
                Peer.Status.ACTIVE: {Peer.Status.LOGIN,
                                     Peer.Status.AUTH,
                                     Peer.Status.CONFIG,
                                     Peer.Status.ACTIVE},
            }

            # if not in map, return exact match
            if self not in applicable_map:
                return self == test_status

            # return if applicable
            return test_status in applicable_map[self]


    PING_TIMEOUT = 130

    def __init__(self, addr: tuple) -> None:
        self.addr: tuple = addr
        self.auth_salt: bytes|None = None
        self.status: Peer.Status = Peer.Status.LOGIN
        self.peer_id: int = 0
        self.connect_time: float = time()
        self.active_time: float = time()
        self.config: dict[str, str] = dict()
        self.units: dict[int, Unit] = dict()

    @property
    def logname(self) -> str:
        return (self.addr_str if self.peer_id == 0
                else f"{self.peer_id}/{self.addr_str}")

    @property
    def name(self) -> str:
        return str(self.peer_id) if self.peer_id != 0 else self.addr_str

    @property
    def addr_str(self) -> str:
        return f"{self.addr[0]}:{self.addr[1]}"

    def check_timeout(self) -> bool:
        return time() - self.active_time < self.PING_TIMEOUT

    def update_active(self) -> None:
        self.active_time = time()

    def update_unit(self, unit_id: int) -> None:
        if unit_id not in self.units:
            logging.info(f"Unit {unit_id} added to {self.logname}")
            self.units[unit_id] = Unit(unit_id)
        self.units[unit_id].update_active()

    def die(self) -> None:
        self.status = Peer.Status.DEAD
        self.peer_id = 0

    def __str__(self) -> str:
        return f"{self.logname} status:{self.status.name}"

    def __repr__(self) -> str:
        return f"<Peer '{self.logname}'>"


class PeerKeeper:
    def __init__(self) -> None:
        self.peers: set[Peer] = set()

    def maintain(self) -> None:
        # Check timeouts
        for peer in self.peers:
            # check unit timeouts:
            tout_unit_ids = [unit_id for unit_id, unit in peer.units.items()
                             if not unit.check_timeout()]

            for unit_id in tout_unit_ids:
                logging.info(f"Unit {unit_id} removed from {peer.logname}")
                del peer.units[unit_id]

            if not peer.check_timeout():
                logging.info(f"Peer {peer.logname} timed out")
                peer.die()

        # remove dead peers
        dead_peers = set(peer for peer in self.peers
                         if peer.status == Peer.Status.DEAD)

        if len(dead_peers) > 0:
            logging.debug(f"Removing dead peers {dead_peers}")
            self.peers -= dead_peers

        logging.debug(
            "Upkeep peers" +
            ("".join(["\n - " + str(peer) for peer in self.peers])))

    def get_by_addr(self, addr: tuple) -> Peer:
        addr_map: dict[tuple, Peer] = {peer.addr: peer for peer in self.peers}
        if addr in addr_map:
            return addr_map[addr]

        peer = Peer(addr)
        logging.info(f"Peer {peer.logname} connected")
        self.peers.add(peer)
        return peer

    def get_by_id(self, peer_id: int) -> set[Peer]:
        return {peer for peer in self.peers if peer.peer_id == peer_id}

    def get_by_unit(self, unit_id: int) -> set[Peer]:
        return {peer for peer in self.peers if unit_id in peer.units}

    def get_all(self) -> set[Peer]:
        return self.peers

    def get_active(self) -> set[Peer]:
        return {peer for peer in self.peers
                if peer.status == Peer.Status.ACTIVE}
