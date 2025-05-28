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
    pass


class DMRPL2BadDataException(Exception):
    """
    Exception raised when L2 data is invalid or corrupted.
    """
    pass


class FactoryException(Exception):
    pass


class DMRPUnknownPacketTypeException(FactoryException):
    """
    Exception raised when the packet factory cannot recognize the packet type
    from the given input data.
    """
    pass
