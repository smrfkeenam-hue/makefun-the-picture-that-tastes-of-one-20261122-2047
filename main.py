"""Picture that tastes of one ingredient — grilled salmon hero.

Validates the bundled entry image and copies it to /output/entry.png.

The entry image is a single glistening grilled salmon fillet: charred
edges, flaking pink-orange flesh, butter gloss, wisps of steam, a lemon
wedge and dill on dark slate, warm golden light. It is generated fresh in
this session and shipped in the repository as entry.png; this program only
checks it against the gate (whole PNG, at most 1,048,576 bytes, at most
1024 x 1024 pixels) and copies it byte for byte to the output directory,
so every run produces the identical file.
"""

import hashlib
import os
import shutil
import struct
import sys
import zlib

MAX_BYTES = 1_048_576
MAX_DIMENSION = 1024

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "entry.png")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
OUTPUT = os.path.join(OUTPUT_DIR, "entry.png")


def read_png_dimensions(path):
    """Width and height of a PNG, read from its IHDR chunk."""
    with open(path, "rb") as handle:
        header = handle.read(33)
    if len(header) < 33 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    if header[12:16] != b"IHDR":
        raise ValueError("PNG has no IHDR chunk")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def validate_png(path):
    """Check the file is a whole PNG within the gate limits."""
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise ValueError(f"entry.png is {size} bytes, over the 1 MiB limit")
    width, height = read_png_dimensions(path)
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValueError(f"entry.png is {width}x{height}, over 1024x1024")
    # Walk the chunk stream so a truncated file is refused, collecting
    # the IDAT payload as we go so it can be decompressed whole.
    with open(path, "rb") as handle:
        data = handle.read()
    pos = 8
    seen_iend = False
    idat = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data):
            raise ValueError("truncated PNG chunk")
        if chunk_type == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        if chunk_type == b"IEND":
            seen_iend = True
            break
        pos = end
    if not seen_iend:
        raise ValueError("PNG has no IEND chunk")
    # The IDAT stream must decompress cleanly.
    zlib.decompress(bytes(idat))
    return size, width, height


def main():
    size, width, height = validate_png(SOURCE)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    shutil.copyfile(SOURCE, OUTPUT)
    with open(SOURCE, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    print(f"entry.png: {width}x{height}, {size} bytes, sha256 {digest}")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, zlib.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
