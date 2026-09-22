"""Install a pinned Flora release into the Python environment running this script."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import sysconfig
import tempfile
import urllib.error
import urllib.request

DEFAULT_VERSION = "0.1.1"
RELEASES = Path(__file__).resolve().parent / "releases"
REPOSITORY = "https://github.com/xio-md/Flora-runtime"


def compatible_tag() -> str:
    if (sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}
            or struct.calcsize("P") != 8 or sys.implementation.name != "cpython"
            or sys.version_info[:2] != (3, 13) or sysconfig.get_config_var("Py_GIL_DISABLED")):
        raise ValueError("This release requires Windows x64 and CPython 3.13 (regular GIL build).")
    return "cp313-cp313-win_amd64"


def release_asset(version: str) -> dict:
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+|\.post\d+)?", version):
        raise ValueError("Invalid release version")
    path = RELEASES / f"{version}.json"
    if not path.is_file():
        raise ValueError(f"No manifest for {version}; update this checkout or select an available version.")
    release = json.loads(path.read_text(encoding="utf-8"))
    if (release.get("schema") != "flora.release.v1" or release.get("version") != version
            or release.get("geophys_adapter_abi") != "geophys.flora_adapter.v4"):
        raise ValueError("Invalid or incompatible release manifest")
    tag = compatible_tag()
    filename = f"flora_render-{version}-{tag}.whl"
    assets = [item for item in release["assets"] if item.get("filename") == filename]
    if len(assets) != 1:
        raise ValueError(f"Release has no unique compatible wheel: {filename}")
    asset = assets[0]
    if (asset.get("url") != f"{REPOSITORY}/releases/download/v{version}/{filename}"
            or not re.fullmatch(r"[0-9a-f]{64}", asset.get("sha256", ""))
            or type(asset.get("size")) is not int or asset["size"] <= 0):
        raise ValueError("Invalid wheel URL, size or checksum in release manifest")
    return asset


def verify_wheel(path: Path, asset: dict) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Wheel is missing: {path}")
    if path.stat().st_size != asset["size"]:
        raise ValueError(f"Wheel size mismatch: {path.name}")
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != asset["sha256"]:
        raise ValueError(f"Wheel SHA-256 mismatch: {path.name}; installation refused")


def install(version: str, wheel_dir: Path | None, offline: bool) -> None:
    asset = release_asset(version)
    if offline and wheel_dir is None:
        raise ValueError("--offline requires --wheel-dir containing Flora and its dependency wheels")
    with tempfile.TemporaryDirectory(prefix="flora-install-") as work:
        if wheel_dir is not None:
            path = wheel_dir.resolve() / asset["filename"]
        else:
            path = Path(work) / asset["filename"]
            request = urllib.request.Request(asset["url"], headers={"User-Agent": "Flora-runtime-installer"})
            try:
                with urllib.request.urlopen(request, timeout=60) as source, path.open("wb") as output:
                    total = 0
                    while block := source.read(1024 * 1024):
                        total += len(block)
                        if total > asset["size"]:
                            raise ValueError("Download exceeds the published wheel size")
                        output.write(block)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise RuntimeError(f"Release v{version} is not published yet or its asset is missing. "
                                       "For a local delivery, use --wheel-dir.") from exc
                raise
        verify_wheel(path, asset)
        command = [sys.executable, "-m", "pip", "install", "--upgrade", str(path)]
        if wheel_dir is not None:
            command.extend(["--find-links", str(wheel_dir.resolve())])
        if offline:
            command.append("--no-index")
        subprocess.run(command, check=True)
    subprocess.run([sys.executable, "-I", "-m", "flora_runtime"], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--wheel-dir", type=Path, help="Use a local wheel instead of downloading it")
    parser.add_argument("--offline", action="store_true", help="Also resolve dependencies only from --wheel-dir")
    args = parser.parse_args()
    try:
        install(args.version, args.wheel_dir, args.offline)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Flora installation failed: {exc}\n")


if __name__ == "__main__":
    main()
