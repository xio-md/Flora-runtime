"""Installer failure boundaries; no network, GPU or pip modifications."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("flora_installer", Path(__file__).resolve().parents[1] / "install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_default_release_is_the_self_contained_wheel(self):
        with patch.object(installer, "compatible_tag", return_value="cp313-cp313-win_amd64"):
            asset = installer.release_asset(installer.DEFAULT_VERSION)
        self.assertEqual(installer.DEFAULT_VERSION, "0.1.1")
        requirements = (installer.RELEASES.parent / "requirements.txt").read_text()
        self.assertEqual(requirements.strip(), f"flora-render @ {asset['url']}#sha256={asset['sha256']}")

    def test_release_has_exact_pinned_github_asset(self):
        with patch.object(installer, "compatible_tag", return_value="cp313-cp313-win_amd64"):
            asset = installer.release_asset("0.1.1")
        self.assertEqual(asset["filename"], "flora_render-0.1.1-cp313-cp313-win_amd64.whl")
        self.assertIn("/releases/download/v0.1.1/", asset["url"])

    def test_version_cannot_escape_manifest_directory(self):
        with self.assertRaises(ValueError):
            installer.release_asset("../0.1.1")

    def test_unsupported_python_is_rejected_before_download(self):
        with patch.object(installer.sys, "version_info", (3, 12)), self.assertRaises(ValueError):
            installer.compatible_tag()

    def test_tampered_wheel_never_reaches_pip(self):
        asset = dict(filename="test.whl", size=4, sha256=hashlib.sha256(b"good").hexdigest())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / asset["filename"]
            path.write_bytes(b"evil")
            with patch.object(installer, "release_asset", return_value=asset), \
                    patch.object(installer.subprocess, "run") as run, self.assertRaises(ValueError):
                installer.install("0.1.1", Path(folder), True)
            run.assert_not_called()

    def test_offline_install_uses_current_interpreter_and_no_index(self):
        asset = dict(filename="test.whl", size=4, sha256=hashlib.sha256(b"good").hexdigest())
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / asset["filename"]).write_bytes(b"good")
            with patch.object(installer, "release_asset", return_value=asset), \
                    patch.object(installer.subprocess, "run") as run:
                installer.install("0.1.1", Path(folder), True)
            command = run.call_args_list[0].args[0]
            self.assertEqual(command[:3], [installer.sys.executable, "-m", "pip"])
            self.assertIn("--no-index", command)
            self.assertEqual(run.call_args_list[1].args[0][-1], "flora_runtime")

    def test_manifest_cannot_redirect_to_another_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            original = json.loads((installer.RELEASES / "0.1.1.json").read_text())
            original["assets"][0]["url"] = "https://example.com/test.whl"
            (Path(folder) / "0.1.1.json").write_text(json.dumps(original))
            with patch.object(installer, "RELEASES", Path(folder)), \
                    patch.object(installer, "compatible_tag", return_value="cp313-cp313-win_amd64"), \
                    self.assertRaises(ValueError):
                installer.release_asset("0.1.1")


if __name__ == "__main__":
    unittest.main()
