class DMRPFieldOutOfRangeException(Exception):
    """
    Exception raised when a packet field value is out of the allowed or expected range.

    Attributes:
        field: The name or identifier of the problematic field.
        typename: The expected type or range description for the field.
    """
    def __init__(self, field, typename) -> None:
        super().__init__(f"Field out of range: {field} must be {typename}")


class DMRPUnknownPacketTypeException(Exception):
    """
    Exception raised when the packet factory cannot recognize the packet type
    from the given input data.
    """
    pass


class DMRPBadPacket(Exception):
    """
    Exception raised when a packet is structurally invalid or corrupted.
    """
    pass
