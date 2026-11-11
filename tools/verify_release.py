"""Audit a local release without importing native code or installing anything."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


RR_PAYLOAD = {"geophys_dlss_rr.dll", "nvngx_dlssd.dll", "dlss_agx.ptx", "path_trace.ptx", "path_trace_rr.ptx"}
RR_SDK_FILES = {
    "flora_runtime/bin/windows-x64/nvngx_dlssd.dll":
        "b49435ae346f227feafe7bbe937d88277ea0ee7323975ec06488f377fdb46cee",
    "flora_runtime/licenses/NVIDIA-DLSS-SDK.txt":
        "3027f23ca5a46dd9cb8183fbd522983a86f64d7daac5982912bf9f214671f294",
}


def verify_native_payload(manifest: dict, archive: zipfile.ZipFile):
    platform = manifest["platform_tag"]
    names = set(archive.namelist())
    if platform == "linux_x86_64":
        native = {"FloraRenderPyNative.so", "flora-vlm-bake", "flora-vlm-inspect", "flora-vlm-delta"}
        folder = "flora_runtime/bin/linux-x64/"
        if (manifest.get("linux_baseline") != {"id": "ubuntu", "version_id": "24.04", "libc": "glibc", "libc_min": "2.39"}
                or manifest.get("qualification") != {"status": "candidate", "gpu": "not_run"}
                or manifest.get("capabilities") != {"external_gpu_interop": False}):
            raise ValueError("Incorrect Linux candidate support declaration")
        for name in native - {"FloraRenderPyNative.so"}:
            if folder + name not in names or not (archive.getinfo(folder + name).external_attr >> 16) & stat.S_IXUSR:
                raise ValueError(f"Missing Linux executable permission: {name}")
    elif platform == "win_amd64":
        native = {"FloraRenderPyNative.pyd", "flora-vlm-bake.exe", "flora-vlm-inspect.exe", "flora-vlm-delta.exe"}
        folder = "flora_runtime/bin/windows-x64/"
        if "bundled_msvc" in manifest:
            libraries = {"msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"}
            if (manifest["bundled_msvc"].get("deployment") != "app-local"
                    or set(manifest["bundled_msvc"].get("files", [])) != libraries):
                raise ValueError("Incorrect app-local VC runtime declaration")
            native.update(libraries)
        rr = manifest.get("capabilities", {}).get("dlss_rr", False)
        if type(rr) is not bool:
            raise ValueError("Invalid DLSS RR capability declaration")
        if rr:
            if manifest.get("dlss_sdk") != "310.9.16":
                raise ValueError("Unreviewed DLSS RR SDK version")
            for name, expected in RR_SDK_FILES.items():
                if name not in names or hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ValueError(f"Invalid public NVIDIA SDK payload: {name}")
            native.update(RR_PAYLOAD)
    else:
        raise ValueError("Unsupported wheel platform")
    if {name for name in names if name.startswith("flora_runtime/bin/")} != {folder + name for name in native}:
        raise ValueError("Unexpected or missing native payload files")


def verify(directory: Path):
    release = json.loads((directory / "release.json").read_text(encoding="utf-8"))
    if release["schema"] != "flora.release.v1":
        raise ValueError("Unknown release schema")
    for asset in release["assets"]:
        filename = asset["filename"]
        platform = asset["platform_tag"]
        if (platform not in {"win_amd64", "linux_x86_64"} or Path(filename).name != filename
                or "\\" in filename or ":" in filename
                or filename != f"flora_render-{release['version']}-cp313-cp313-{platform}.whl"):
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
                if stat.S_ISLNK(archive.getinfo(name).external_attr >> 16):
                    raise ValueError(f"Unexpected symlink: {name}")
                if (path.suffix.lower() not in {".py", ".pyd", ".exe", ".dll", ".so", ".txt", ".md", ".json", ""}
                        and not (path.parent.as_posix() == "flora_runtime/bin/windows-x64"
                                 and path.name in RR_PAYLOAD)):
                    raise ValueError(f"Unapproved payload type (source/debug/build artifact): {name}")
            manifest = json.loads(archive.read("flora_runtime/runtime.json"))
            verify_native_payload(manifest, archive)
            if (manifest["version"] != release["version"] or manifest["shaders"] != "embedded"
                    or manifest["platform_tag"] != platform
                    or manifest["python_tag"] != asset["python_tag"] or manifest["abi_tag"] != asset["abi_tag"]
                    or manifest["geophys_adapter_abi"] != release["geophys_adapter_abi"]):
                raise ValueError("Wheel/release contract mismatch")
            if manifest.get("capabilities", {}) != release.get("capabilities", {}):
                raise ValueError("Wheel/release capability mismatch")
            if platform == "linux_x86_64":
                for key in ("linux_baseline", "qualification", "capabilities"):
                    if manifest[key] != release.get(key):
                        raise ValueError(f"Linux release/wheel mismatch: {key}")
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
    sums = directory / "SHA256SUMS.txt"
    if sums.is_file():
        checked = set()
        for line in sums.read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            if (not re.fullmatch(r"[0-9a-f]{64}", digest) or Path(name).name != name
                    or "\\" in name or ":" in name or name in checked):
                raise ValueError("Invalid SHA256SUMS entry")
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Attachment hash mismatch: {name}")
            checked.add(name)
        if not ({asset["filename"] for asset in release["assets"]} | {"release.json", "requirements.txt"}).issubset(checked):
            raise ValueError("SHA256SUMS does not cover the release files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    verify(parser.parse_args().directory)
