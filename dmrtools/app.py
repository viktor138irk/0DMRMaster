import logging
import time

from abc import ABC, abstractmethod

from .call import Call
from .dmrproto import DMRPPacketData


class AppException(Exception):
    pass


class IAppDispatcher(ABC):
    """
    Dispatcher interface for app
    """
    @abstractmethod
    def inject_packet(self, p: DMRPPacketData) -> None: ...


class IAppCallInterceptor(ABC):
    @abstractmethod
    def process_call_packet(self, call: Call, p: DMRPPacketData) -> None: ...


class App(ABC):
    def __init__(self) -> None:
        self.dispatcher: IAppDispatcher|None = None

    @abstractmethod
    def get_name(self) -> str: ...


class AppKeeper:
    def __init__(self, dispatcher: IAppDispatcher):
        self.dispatcher: IAppDispatcher = dispatcher
        self.apps: list[App] = []

    def register(self, app: App) -> bool:
        logging.info(f"Registered app '{app.get_name()}'    ")
        app.dispatcher = self.dispatcher
        self.apps.append(app)
        return True

    def process_call_packet(self, call: Call, p: DMRPPacketData) -> None:
        for app in self.apps:
            if isinstance(app, IAppCallInterceptor):
                app.process_call_packet(call, p)


