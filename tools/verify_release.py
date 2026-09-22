"""Audit a local release without importing native code or installing anything."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile


def verify(directory: Path):
    release = json.loads((directory / "release.json").read_text(encoding="utf-8"))
    if release["schema"] != "flora.release.v1":
        raise ValueError("Unknown release schema")
    for asset in release["assets"]:
        filename = asset["filename"]
        if Path(filename).name != filename or not filename.endswith("-cp313-cp313-win_amd64.whl"):
            raise ValueError("Invalid wheel filename")
        wheel = directory / filename
        data = wheel.read_bytes()
        if len(data) != asset["size"] or hashlib.sha256(data).hexdigest() != asset["sha256"]:
            raise ValueError("Release wheel hash/size mismatch")
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate archive entries")
            info = f"flora_render-{release['version']}.dist-info"
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                    raise ValueError(f"Unsafe archive path: {name}")
                if path.parts[0] not in {"flora", "flora_backend", "flora_runtime", info}:
                    raise ValueError(f"Unexpected payload root: {name}")
                if path.suffix.lower() not in {".py", ".pyd", ".exe", ".dll", ".txt", ".md", ".json", ""}:
                    raise ValueError(f"Unapproved payload type (source/debug/build artifact): {name}")
            manifest = json.loads(archive.read("flora_runtime/runtime.json"))
            if "bundled_msvc" in manifest:
                required = {f"flora_runtime/bin/windows-x64/{name}"
                            for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")}
                if not required.issubset(names) or manifest["bundled_msvc"]["deployment"] != "app-local":
                    raise ValueError("Incomplete app-local VC runtime")
            if (manifest["version"] != release["version"] or manifest["shaders"] != "embedded"
                    or manifest["geophys_adapter_abi"] != release["geophys_adapter_abi"]):
                raise ValueError("Wheel/release contract mismatch")
            payload = {name for name in names if not name.startswith(info + "/")
                       and name != "flora_runtime/runtime.json"}
            if payload != set(manifest["files"]):
                raise ValueError("Wheel contains missing or unlisted payload files")
            for name, digest in manifest["files"].items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    raise ValueError(f"Corrupt payload: {name}")
            records = list(csv.reader(io.StringIO(archive.read(f"{info}/RECORD").decode())))
            if {row[0] for row in records} != set(names) or len(records) != len(names):
                raise ValueError("RECORD does not cover every wheel member exactly once")
            for name, digest, size in records:
                if name == f"{info}/RECORD":
                    continue
                content = archive.read(name)
                expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
                if digest != expected or int(size) != len(content):
                    raise ValueError(f"Invalid wheel RECORD: {name}")
            print(f"PASS {filename}: {len(payload)} approved payload files; hashes and RECORD verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    verify(parser.parse_args().directory)
