"""Species sprites for the web page (002 research R3), read from the vendored decomp.

- `front`: res/pokemon/<species>/male_front.png, falling back to female_front.png (female-only
  species such as Blissey). 160x80, two 80x80 frames; the page shows the first frame with CSS.
- `icon`: res/pokemon/<species>/icon.png. 32x64, two 32x32 frames.

The files are 4-bit indexed PNGs whose palette index 0 is an opaque background colour. A one-entry
tRNS chunk (index 0 -> alpha 0) is inserted right after PLTE, using only the standard library.
Species keys are checked against the decomp folder names, so a request never builds a path from
raw input. Nothing is written to disk; results are cached in memory.
"""

from __future__ import annotations

import functools
import struct
import zlib

from platsim.pins import DECOMP_ROOT

POKEMON_DIR = DECOMP_ROOT / "res" / "pokemon"
KINDS = {"front": ("male_front.png", "female_front.png"), "icon": ("icon.png",)}
_NOT_SPECIES = {"egg", "bad_egg"}
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


@functools.cache
def allowed_species() -> frozenset[str]:
    if not POKEMON_DIR.is_dir():
        return frozenset()
    return frozenset(p.name for p in POKEMON_DIR.iterdir() if p.is_dir() and p.name not in _NOT_SPECIES)


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def with_transparent_index0(png: bytes) -> bytes:
    """Insert tRNS (index 0 transparent) after PLTE. A PNG without PLTE, or that already has tRNS,
    is returned unchanged."""
    if png[:8] != _PNG_SIG:
        return png
    out, i, plte_end, has_trns = bytearray(png[:8]), 8, None, False
    while i + 8 <= len(png):
        n = struct.unpack(">I", png[i:i + 4])[0]
        kind = png[i + 4:i + 8]
        end = i + 12 + n
        out += png[i:end]
        if kind == b"PLTE":
            plte_end = len(out)
        elif kind == b"tRNS":
            has_trns = True
        i = end
    if plte_end is None or has_trns:
        return png
    return bytes(out[:plte_end]) + _chunk(b"tRNS", b"\x00") + bytes(out[plte_end:])


@functools.cache
def sprite_png(species: str, kind: str) -> bytes | None:
    if kind not in KINDS or species not in allowed_species():
        return None
    for name in KINDS[kind]:
        f = POKEMON_DIR / species / name
        if f.is_file():
            return with_transparent_index0(f.read_bytes())
    return None
