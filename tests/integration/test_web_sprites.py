"""002 T006: GET /api/sprites/{species}/{kind}.png (contracts/http-api.md, research R3).

The decomp sprites are 4-bit indexed PNGs whose index 0 is an opaque background colour and which
have no tRNS chunk (observed for infernape/luxray/gardevoir/blissey). The server adds a one-entry
tRNS chunk (index 0 -> alpha 0) right after PLTE. Game facts used:
- pokeplatinum/res/pokemon/blissey/ has female_front.png but no male_front.png (fallback case).
"""

from __future__ import annotations

import struct

from fastapi.testclient import TestClient

from _web_helpers import make_app
from platsim.pins import DECOMP_ROOT

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    assert data[:8] == PNG_SIG
    out, i = [], 8
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        out.append((data[i + 4:i + 8], data[i + 8:i + 8 + n]))
        i += 12 + n
    return out


def test_sprites(tmp_path, catalog):
    client = TestClient(make_app(tmp_path, catalog))

    # Positive control: the source file has no tRNS; the served one has it right after PLTE.
    src = (DECOMP_ROOT / "res/pokemon/infernape/male_front.png").read_bytes()
    assert b"tRNS" not in [t for t, _ in _chunks(src)]
    r = client.get("/api/sprites/infernape/front.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    types = [t for t, _ in _chunks(r.content)]
    assert types[types.index(b"PLTE") + 1] == b"tRNS"
    assert dict(_chunks(r.content))[b"tRNS"][:1] == b"\x00"
    assert "max-age" in r.headers.get("cache-control", "")

    # Female-only species: falls back to female_front.png.
    assert not (DECOMP_ROOT / "res/pokemon/blissey/male_front.png").exists()
    assert client.get("/api/sprites/blissey/front.png").status_code == 200

    assert client.get("/api/sprites/infernape/icon.png").status_code == 200
    for bad in ("/api/sprites/notamon/front.png", "/api/sprites/infernape/back.png",
                "/api/sprites/..%2Fetc/front.png", "/api/sprites/egg/front.png"):
        assert client.get(bad).status_code == 404, bad

    assert client.get("/api/sprites/infernape/front.png").content == r.content
