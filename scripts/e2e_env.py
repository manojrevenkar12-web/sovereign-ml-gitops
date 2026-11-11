"""Print the environment for deploy/compose/e2e.yaml from tenants/*.yaml, and prepare a copy of the
artifacts with one flipped byte for the integrity test.

Usage: python scripts/e2e_env.py TAMPERED_DIR >> "$GITHUB_ENV"
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from sov.config import load_tenants

from _common import ROOT


def main() -> None:
    tampered = Path(sys.argv[1])
    specs = load_tenants()
    env = {}
    for name in ("stadt-nordhafen", "stadt-weidenbach"):
        short = name.split("-", 1)[1].upper()
        env[f"{short}_BASE"] = specs[name]["model"]["base"]
        env[f"{short}_ADAPTER"] = specs[name]["model"]["adapter"]
    tampered.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "artifacts").glob("*.npz"):
        shutil.copy(f, tampered / f.name)
    victim = tampered / f"{env['NORDHAFEN_ADAPTER'].split(':')[1]}.npz"
    data = bytearray(victim.read_bytes())
    data[len(data) // 2] ^= 0x01
    victim.write_bytes(bytes(data))
    for f in tampered.iterdir():
        f.chmod(0o644)
    tampered.chmod(0o755)
    env["TAMPERED_DIR"] = str(tampered.resolve())
    for k, v in env.items():
        print(f"{k}={v}")


if __name__ == "__main__":
    main()
