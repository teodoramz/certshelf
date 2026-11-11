"""Badge images, embedded as data: URIs (GitHub shows SVGs as <img>, which can't load outside images)."""
from __future__ import annotations

import base64
import re
import urllib.request
from pathlib import Path

MAX_BYTES = 2_000_000
CREDLY = re.compile(r"^https://images\.credly\.com/images/([^/]+)/([^/?#]+)$")
USER_AGENT = "certshelf (+https://github.com/teodoramz/certshelf)"


def _mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    head = data[:512].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "image/svg+xml"
    return None


def _uri(data: bytes) -> str | None:
    mime = _mime(data)
    if not mime or len(data) > MAX_BYTES:
        return None
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _download(url: str, urlopen) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as reply:
            return reply.read(MAX_BYTES + 1)
    except (OSError, ValueError):
        return None


def load_image(ref: str | None, root: Path, urlopen=urllib.request.urlopen) -> str | None:
    """A data: URI for an http(s) URL or a path inside `root`; None if it is missing or not an image."""
    if not ref:
        return None
    if ref.startswith(("http://", "https://")):
        candidates = [ref]
        credly = CREDLY.match(ref)
        if credly:  # a 160px rendition is a quarter of the size; not every image has one
            candidates.insert(0, f"https://images.credly.com/size/160x160/images/{credly.group(1)}/{credly.group(2)}")
        for url in candidates:
            data = _download(url, urlopen)
            uri = _uri(data) if data else None
            if uri:
                return uri
        return None
    root = Path(root).resolve()
    path = (root / ref).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return _uri(path.read_bytes()[: MAX_BYTES + 1])
