from abc import ABC, abstractmethod
from typing import Any

from .exceptions import DMRPFieldOutOfRangeException


class DMRPFieldBase(ABC):
    def __init__(self, name: str, offset: int, bytelen: int) -> None:
        self.name, self.offset, self.bytelen = name, offset, bytelen
        self.eoffset = offset + bytelen
        self.typename = f"bytes{self.bytelen}"

    def get(self, obj) -> bytes:
        return bytes(obj._data[self.offset:self.eoffset])

    def set(self, obj, value: bytes):
        if not isinstance(value, bytes) or self.bytelen != len(value):
            raise DMRPFieldOutOfRangeException(self.name, self.typename)
        obj._data[self.offset:self.eoffset] = value

    @abstractmethod
    def __get__(self, obj, cls = None) -> Any:
        pass

    @abstractmethod
    def __set__(self, obj, value: Any) -> None:
        pass


class DMRPFieldBytes(DMRPFieldBase):
    def __get__(self, obj, cls = None) -> bytes:
        return self.get(obj)

    def __set__(self, obj, value: bytes) -> None:
        self.set(obj, value)


class DMRPFieldStr(DMRPFieldBase):
    def __init__(self, name: str, offset: int, bytelen: int,
                 pad_with: bytes = b'\x20') -> None:
        super().__init__(name, offset, bytelen)
        self.typename = 'str'
        self.pad_with = pad_with

    def __get__(self, obj, cls = None) -> str:
        return (self.get(obj).strip(b'\x20\x00')
                .decode(encoding='ascii', errors='ignore'))

    def __set__(self, obj, value: str) -> None:
        bvalue = value.encode()
        if len(bvalue) > self.bytelen:
            bvalue = bvalue[:self.bytelen]
        bvalue = bvalue.ljust(self.bytelen, self.pad_with)
        self.set(obj, bvalue)


class DMRPFieldInt(DMRPFieldBase):
    def __init__(self, name: str, offset: int, bytelen: int) -> None:
        super().__init__(name, offset, bytelen)
        self.typename = f"uint{str(bytelen * 8)}"

    def __get__(self, obj, cls = None) -> int:
        return int.from_bytes(self.get(obj), byteorder="big")

    def __set__(self, obj, value: int) -> None:
        if not (0 <= value < 1<<(self.bytelen * 8)):
            raise DMRPFieldOutOfRangeException(self.name, self.typename)
        self.set(obj, value.to_bytes(self.bytelen, byteorder="big"))


