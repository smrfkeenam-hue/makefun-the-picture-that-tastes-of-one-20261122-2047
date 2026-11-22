#!/usr/bin/env python3
"""Entry program for the-picture-that-tastes-of-one-20261122-2047.

Validates the bundled hero image (entry.png, next to this file) as a whole,
well-formed PNG inside the competition's size limits, then copies it byte
for byte to /output/entry.png (or $MAKEFUN_OUTPUT_DIR outside a container).

The copy is byte-identical by construction: the file is read once, checked,
and the exact bytes written out. Running this program twice therefore
produces byte-identical outputs.
"""

import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "entry.png")

MAX_BYTES = 1_048_576
MAX_WIDTH = 1024
MAX_HEIGHT = 1024

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class InvalidImage(ValueError):
    """Raised when entry.png fails any validation step."""


def _check(condition, message):
    if not condition:
        raise InvalidImage(message)


def validate_png(data):
    """Walk a PNG byte by byte and return (width, height).

    Checks the signature, the IHDR chunk (dimensions, bit depth, colour
    type, compression/filter/interlace), every chunk's CRC, that IDAT data
    decompresses cleanly, and that the file ends with IEND. Nothing is
    decoded into pixels: the gate only needs a whole, well-formed file.
    """
    _check(len(data) >= 8, "file too short to be a PNG")
    _check(data[:8] == PNG_SIGNATURE, "not a PNG signature")

    pos = 8
    seen_ihdr = False
    seen_idat = False
    seen_iend = False
    width = height = None
    idat = bytearray()

    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        _check(pos + 12 + length <= len(data),
               "chunk %r overruns the file" % ctype)
        payload = data[pos + 8:pos + 8 + length]
        stored_crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        actual_crc = zlib.crc32(ctype + payload) & 0xFFFFFFFF
        _check(stored_crc == actual_crc,
               "chunk %r has a bad CRC" % ctype)

        if ctype == b"IHDR":
            _check(not seen_ihdr, "duplicate IHDR chunk")
            _check(length == 13, "IHDR chunk has the wrong length")
            width, height, depth, colour, comp, filt, interlace = struct.unpack(
                ">IIBBBBB", payload)
            _check(width > 0 and height > 0, "IHDR dimensions are zero")
            _check(depth in (1, 2, 4, 8, 16), "bad IHDR bit depth")
            _check(colour in (0, 2, 3, 4, 6), "bad IHDR colour type")
            _check(comp == 0 and filt == 0, "bad IHDR compression/filter")
            _check(interlace in (0, 1), "bad IHDR interlace method")
            seen_ihdr = True
        elif ctype == b"IDAT":
            _check(seen_ihdr, "IDAT appears before IHDR")
            idat.extend(payload)
            seen_idat = True
        elif ctype == b"IEND":
            _check(length == 0, "IEND chunk carries data")
            _check(seen_idat, "IEND appears before any IDAT")
            seen_iend = True
            pos += 12 + length
            break
        else:
            _check(seen_ihdr, "chunk %r appears before IHDR" % ctype)

        pos += 12 + length

    _check(seen_ihdr, "no IHDR chunk found")
    _check(seen_idat, "no IDAT chunk found")
    _check(seen_iend, "no IEND chunk found")
    _check(pos == len(data), "trailing bytes after IEND")

    # The compressed image data must inflate without error, and the
    # inflated bytes must be exactly the scanlines the IHDR promises
    # (one filter byte per row plus the row's pixels), so truncated
    # image data that still inflates is caught too.
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    bits_per_pixel = depth * channels
    row_bytes = (width * bits_per_pixel + 7) // 8
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise InvalidImage("IDAT data does not decompress: %s" % exc)
    if interlace == 0:
        _check(len(raw) == height * (row_bytes + 1),
               "IDAT inflates to %d bytes, expected %d scanline bytes"
               % (len(raw), height * (row_bytes + 1)))

    return width, height


def main():
    with open(SOURCE, "rb") as handle:
        data = handle.read()

    _check(len(data) <= MAX_BYTES,
           "entry.png is %d bytes, over the %d-byte limit"
           % (len(data), MAX_BYTES))

    width, height = validate_png(data)

    _check(width <= MAX_WIDTH and height <= MAX_HEIGHT,
           "entry.png is %dx%d, over the %dx%d limit"
           % (width, height, MAX_WIDTH, MAX_HEIGHT))

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")
    with open(out_path, "wb") as handle:
        handle.write(data)

    print("entry.png: %dx%d, %d bytes" % (width, height, len(data)))
    print("wrote %s" % out_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except InvalidImage as exc:
        print("invalid entry.png: %s" % exc, file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print("cannot read or write: %s" % exc, file=sys.stderr)
        sys.exit(1)
