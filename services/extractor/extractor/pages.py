"""Reads the pages of a clean ZIP in the order of its manifest (contracts/manifest.v1)."""
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass

_SHA = re.compile(r'^[0-9a-f]{64}$')
_VERSION = re.compile(r'^1\.(0|[1-9][0-9]*)$')


class BadZip(Exception):
    """The clean ZIP breaks its contract. The checker accepted it, so this is a bug, not bad input."""


@dataclass(frozen=True)
class Page:
    index: int
    sha256: str
    png: bytes


def read_zip(data):
    """Pages in manifest order. Raises BadZip; the message never quotes page content."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        manifest = json.loads(archive.read('manifest.json'))
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        raise BadZip(f'unreadable ZIP or manifest: {type(e).__name__}') from None
    if not isinstance(manifest, dict) or not _VERSION.match(str(manifest.get('schemaVersion', ''))):
        raise BadZip('manifest major version is not 1')
    order = manifest.get('order')
    if not isinstance(order, list) or not order or len(set(order)) != len(order):
        raise BadZip('manifest order must be a non-empty list of unique hashes')
    pages = []
    for i, sha in enumerate(order, 1):
        if not isinstance(sha, str) or not _SHA.match(sha):
            raise BadZip(f'page {i}: not a SHA-256')
        try:
            png = archive.read(f'pages/{sha}.png')
        except KeyError:
            raise BadZip(f'page {i}: file missing') from None
        if hashlib.sha256(png).hexdigest() != sha:
            raise BadZip(f'page {i}: hash differs from its name')
        pages.append(Page(i, sha, png))
    return pages
