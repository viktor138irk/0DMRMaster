from abc import ABC, abstractmethod


class DMRPFieldOutOfRangeException(Exception):
    """
    Exception raised when a packet field value is out of the allowed or expected range.

    Attributes:
        field: The name or identifier of the problematic field.
        typename: The expected type or range description for the field.
    """
    def __init__(self, field, typename) -> None:
        super().__init__(f"Field out of range: {field} must be {typename}")


class DMRPBadPacketException(Exception):
    """
    Exception raised when a packet is structurally invalid or corrupted
    """
    ...

class DMRPL2BadDataException(Exception):
    """
    Exception raised when L2 data is invalid or corrupted.
    """
    ...


class FactoryException(Exception):
    ...


class DMRPUnknownPacketTypeException(FactoryException):
    """
    Exception raised when the packet factory cannot recognize the packet type
    from the given input data.
    """
    ...


class DMRPUnknownLCTypeException(FactoryException):
    """
    Exception raised when the lc analyzer factory cannot recognize the
    lc type from the given input data.
    """
    ...


class CustomMessageException(Exception, ABC):
    @classmethod
    @abstractmethod
    def create_message(cls, msg: str) -> str: ...

    def __init__(self, msg: str):
        super().__init__(self.__class__.create_message(msg))


class EmbLCAssemblerException(CustomMessageException):
    """
    Exception raised on EmbLCAssembler error
    """
    @classmethod
    def create_message(cls, msg: str) -> str:
        return f"Embedded LC failed: {msg}"


class CallLCDecoderException(CustomMessageException):
    """
    Exception raised on CallLCDecoder error
    """
    @classmethod
    def create_message(cls, msg: str) -> str:
        return f"In-call LC decoder failed: {msg}"
