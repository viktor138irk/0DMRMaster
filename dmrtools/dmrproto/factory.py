from abc import ABC, abstractmethod
from typing import Self, Type, NoReturn

from .exceptions import FactoryException


class IFactoryProduced(ABC):
    @abstractmethod
    def __init__(self, data: bytes) -> None:
        pass

    @classmethod
    @abstractmethod
    def detect_by_data(cls, data: bytes) -> bool:
        pass


class BaseFactory(ABC):
    __instance: Self|None = None

    @classmethod
    def fd(cls, data: bytes) -> IFactoryProduced:
        """
        Short singleton version of from_data method
        """
        if cls.__instance is None:
            cls.__instance = cls()
        return cls.__instance.from_data(data)

    def __init__(self,
                 classes: list[Type[IFactoryProduced]]|None = None) -> None:
        self._classes: list[Type[IFactoryProduced]] = (
            classes if classes is not None else [])

    def register(self, cls: Type[IFactoryProduced]) -> None:
        self._classes.append(cls)

    def from_data(self, data: bytes) -> IFactoryProduced:
        """
        Attempts to create an instance of corresponding
        IFactoryProduced-implementing class based on data
        """
        for cls in self._classes:
            if cls.detect_by_data(data):
                return cls(data)

        self.not_found(data)

    def not_found(self, data: bytes) -> NoReturn:
        raise FactoryException(f"No class found for {data.hex()}")
