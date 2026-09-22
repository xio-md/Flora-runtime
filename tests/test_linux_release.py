"""Platform-specific release boundaries, without native imports or a Linux host."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("flora_release_check", ROOT / "tools/verify_release.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


class LinuxReleaseTests(unittest.TestCase):
    def setUp(self):
        self.release = json.loads((ROOT / "releases/0.1.2rc1.json").read_text())
        self.manifest = {key: self.release[key] for key in ("linux_baseline", "qualification", "capabilities")}
        self.manifest["platform_tag"] = "linux_x86_64"

    def archive(self, *, executable=True, extra=None):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for name in ["FloraRenderPyNative.so", "flora-vlm-bake", "flora-vlm-inspect", "flora-vlm-delta"]:
                info = zipfile.ZipInfo("flora_runtime/bin/linux-x64/" + name)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
                archive.writestr(info, b"fixture")
            if extra:
                archive.writestr(extra, b"fixture")
        return zipfile.ZipFile(data)

    def test_linux_install_entry_is_pinned_without_changing_windows_default(self):
        asset = self.release["assets"][0]
        self.assertEqual((ROOT / "requirements-linux.txt").read_text().strip(),
                         f"flora-render @ {asset['url']}#sha256={asset['sha256']}")
        self.assertIn("/v0.1.1/", (ROOT / "requirements.txt").read_text())

    def test_linux_native_payload_passes(self):
        with self.archive() as archive:
            check.verify_native_payload(self.manifest, archive)

    def test_lost_executable_permission_is_rejected(self):
        with self.archive(executable=False) as archive, self.assertRaisesRegex(ValueError, "executable permission"):
            check.verify_native_payload(self.manifest, archive)

    def test_foreign_binary_is_rejected(self):
        with self.archive(extra="flora_runtime/bin/windows-x64/FloraRenderPyNative.pyd") as archive:
            with self.assertRaisesRegex(ValueError, "native payload"):
                check.verify_native_payload(self.manifest, archive)

    def test_unverified_gpu_cannot_be_reported_as_passed(self):
        self.manifest["qualification"] = {"status": "candidate", "gpu": "passed"}
        with self.archive() as archive, self.assertRaisesRegex(ValueError, "support declaration"):
            check.verify_native_payload(self.manifest, archive)


if __name__ == "__main__":
    unittest.main()
