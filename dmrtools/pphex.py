def hexdump(data: bytes, width: int = 16) -> str:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_bytes = ' '.join(f"{b:02X}" for b in chunk)
        ascii_repr = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        lines.append(f"{i:04X}: {hex_bytes:<{width*3}} {ascii_repr}")
    return '\n'.join(lines)


if __name__ == '__main__':
    testdata = (
        b"\x01\x02\x52\x44\x38\x03\xE7\xFD\x26\xE9\xC1\x0F\x33\x4F\x66\xC5"
        b"\x00\x00\x00\x00\xC8\xD0\xE7\x44\x7E\x24\x9D\x07\x3B\x0F\xF4\xA7"
        b"\x9E\x31\x10\x00\x00\x00\x0E\x20\xC6\x1C\xB1\x76\xAF\x94\xE5\x55"
        b"\x37\x58\xAD\xA6\x41\x00\x00"
    )
    print(hexdump(testdata))
