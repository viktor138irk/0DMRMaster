from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Type, ClassVar, NoReturn, Any

from .exceptions import FactoryException


class IFactoryProduced(ABC):
    @abstractmethod
    def __init__(self, data: bytes) -> None: ...

    @classmethod
    @abstractmethod
    def detect_by_data(cls, data: bytes) -> bool: ...


TProduced = TypeVar("TProduced", bound=IFactoryProduced, covariant=True)


class AbstractFactory(Generic[TProduced], ABC):
    _instance: ClassVar[AbstractFactory[Any]|None] = None

    @classmethod
    def fd(cls: Type[AbstractFactory[TProduced]],
           data: bytes) -> TProduced:
        """
        Short singleton version of from_data method
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance.from_data(data)

    def __init__(self,
                 classes: list[Type[TProduced]]|None = None) -> None:
        self._classes: list[Type[TProduced]] = (
            classes if classes is not None else [])

    def register(self, cls: Type[TProduced]) -> None:
        self._classes.append(cls)

    def from_data(self, data: bytes) -> TProduced:
        """
        Attempts to create an instance of corresponding
        TProduced-implementing class based on data
        """
        for cls in self._classes:
            if cls.detect_by_data(data):
                return cls(data)

        self.not_found(data)

    def not_found(self, data: bytes) -> NoReturn:
        raise FactoryException(f"No class found for {data.hex()}")
