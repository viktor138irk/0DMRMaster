from abc import ABC, abstractmethod


class IDatagramReceiver(ABC):
    @abstractmethod
    def recv_dg(self, data: bytes, addr: tuple) -> None: ...


class IDatagramSender(ABC):
    @abstractmethod
    def send_dg(self, data: bytes, addr: tuple) -> None: ...

    @abstractmethod
    def set_receiver(self, receiver: IDatagramReceiver) -> None: ...
