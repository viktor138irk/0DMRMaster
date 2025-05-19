from abc import ABC, abstractmethod


class IDatagramReceiver(ABC):
    @abstractmethod
    def recv_dg(self, data: bytes, addr: tuple) -> None:
        pass


class IDatagramSender(ABC):
    @abstractmethod
    def send_dg(self, data: bytes, addr: tuple) -> None:
        pass

    @abstractmethod
    def set_receiver(self, receiver: IDatagramReceiver) -> None:
        pass

