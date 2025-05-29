import logging

from abc import ABC, abstractmethod

from .dmrproto import calc_password_hash


class IPeerAuth(ABC):
    @abstractmethod
    def allow_peer_id(self, peer_id: int) -> bool: ...

    @abstractmethod
    def check_password(self, peer_id: int, salt: bytes,
                       pass_hash: bytes) -> bool: ...


class AllowAllPeerAuth(IPeerAuth):
    """
    Auth agent to allow any peer id and any password
    """
    def allow_peer_id(self, peer_id: int) -> bool:
        return True

    def check_password(self, peer_id: int, salt: bytes,
                       pass_hash: bytes) -> bool:
        return True


class DenyAllPeerAuth(IPeerAuth):
    """
    Auth agent to deny any peer id and any password
    """
    def allow_peer_id(self, peer_id: int) -> bool:
        logging.warning("Deny all policy active")
        return False

    def check_password(self, peer_id: int, salt: bytes,
                       pass_hash: bytes) -> bool:
        return False


class ListPeerAuth(IPeerAuth):
    """
    Auth agent with list of allowed peers and their passwords
    use empty password to accept any password
    """
    def __init__(self, allowed_peers: dict[int, str]|None = None) -> None:
        """
        allowed_peers in format peer_id -> password
        """
        self.allowed_peers: dict[int, str] = (
            dict() if allowed_peers is None else allowed_peers)

    def allow_peer_id(self, peer_id: int) -> bool:
        return peer_id in self.allowed_peers

    def check_password(self, peer_id: int, salt: bytes,
                       pass_hash: bytes) -> bool:
        if peer_id not in self.allowed_peers:
            return False

        valid_password = self.allowed_peers[peer_id]
        if valid_password == '':
            logging.debug(f"Any password accepted for {peer_id}")
            return True  # Accept any password if empty in config

        return pass_hash == calc_password_hash(salt, valid_password)
