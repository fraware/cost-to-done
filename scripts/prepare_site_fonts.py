"""Materialize original IBM Plex WOFF2 assets from an immutable upstream commit.

Run before serving the static website locally or packaging GitHub Pages.
Downloads occur at build time, never in the visitor's browser. Every blob
is checked against the recorded Git object identity and expected size.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.request import urlopen

COMMIT = "ba3013d72a8419a22c758cc51c44e04ac7ea565b"
BASE = f"https://raw.githubusercontent.com/IBM/plex/{COMMIT}/"
ROOT = Path(__file__).resolve().parents[1] / "docs/fonts"
ASSETS = {
    "IBMPlexSans-Regular.woff2": ("plex-sans", 65080, "9c75d2e7111a534ec1f22efec30395beb4e28c45"),
    "IBMPlexSans-Medium.woff2": ("plex-sans", 69148, "97b0b37efbb6495f3505259eac417b30334084d3"),
    "IBMPlexSans-SemiBold.woff2": ("plex-sans", 69388, "6061208a78b93261b143f6fea70ed4b92f4b4742"),
    "IBMPlexSans-Bold.woff2": ("plex-sans", 65012, "c4beccb1551dc4510d5e1f3a7e62b723cc9f625c"),
    "IBMPlexMono-Regular.woff2": ("plex-mono", 49248, "8bdb4c4b3f8fae88cc2e3c9c744952dccf89b15a"),
}


def validate(data: bytes, size: int, blob: str) -> None:
    identity = hashlib.sha1(f"blob {len(data)}\0".encode() + data,
                            usedforsecurity=False).hexdigest()
    if len(data) != size or data[:4] != b"wOF2" or identity != blob:
        raise ValueError("font blob failed identity, size or WOFF2 validation")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, (package, size, blob) in ASSETS.items():
        target = ROOT / name
        if target.exists():
            validate(target.read_bytes(), size, blob)
        else:
            url = BASE + f"packages/{package}/fonts/complete/woff2/{name}"
            with urlopen(url, timeout=30) as response:
                data = response.read(size + 1)
            validate(data, size, blob)
            # Exclusive creation avoids replacing an existing local font.
            with target.open("xb") as stream:
                stream.write(data)
        print(f"Verified {name}: {size} bytes, Git blob {blob}")


if __name__ == "__main__":
    main()
