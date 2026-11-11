"""Content-addressed model registry. An artifact is addressed by the sha256 of its bytes, and is only
ever loaded after the bytes have been hashed again and match the digest pinned in git.

Locally the registry is a directory; in production it is an S3 bucket (IONOS Object Storage or MinIO on
premises) with the same layout: <hex>.npz next to <hex>.json.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np


class IntegrityError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def pack(arrays: dict[str, np.ndarray]) -> bytes:
    """A .npz with fixed member order and timestamps, so equal weights give an equal digest."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for name in sorted(arrays):
            member = io.BytesIO()
            np.lib.format.write_array(member, np.ascontiguousarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            zf.writestr(info, member.getvalue())
    return buf.getvalue()


def unpack(data: bytes) -> dict[str, np.ndarray]:
    with np.load(io.BytesIO(data), allow_pickle=False) as npz:
        return {k: npz[k] for k in npz.files}


class Registry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str, ext: str) -> Path:
        algo, _, hexd = digest.partition(":")
        if algo != "sha256" or len(hexd) != 64 or any(c not in "0123456789abcdef" for c in hexd):
            raise IntegrityError(f"not a sha256 digest: {digest!r}")
        return self.root / f"{hexd}.{ext}"

    def put(self, arrays: dict[str, np.ndarray], manifest: dict[str, Any]) -> str:
        data = pack(arrays)
        digest = sha256(data)
        self._path(digest, "npz").write_bytes(data)
        meta = dict(manifest, digest=digest, bytes=len(data))
        self._path(digest, "json").write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
        return digest

    def get(self, digest: str) -> dict[str, np.ndarray]:
        path = self._path(digest, "npz")
        if not path.exists():
            raise IntegrityError(f"{digest} is not in the registry")
        data = path.read_bytes()
        if sha256(data) != digest:
            raise IntegrityError(f"{path.name} does not hash to {digest}")
        return unpack(data)

    def manifest(self, digest: str) -> dict[str, Any]:
        return json.loads(self._path(digest, "json").read_text(encoding="utf-8"))

    def size_kb(self, digest: str) -> float:
        return self._path(digest, "npz").stat().st_size / 1024
