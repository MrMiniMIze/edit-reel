import os
import tempfile
import unittest
from unittest import mock

import tests.fixtures  # noqa: F401  (sets sys.path)
import capcut
import check
import common


class CheckTests(unittest.TestCase):
    def test_this_machine_is_ready(self):
        self.assertEqual(check.problems(), [])

    def test_missing_ffmpeg_says_how_to_install(self):
        with mock.patch("shutil.which", return_value=None):
            msgs = check.problems()
        self.assertEqual(len(msgs), 1)
        self.assertIn("brew install ffmpeg-full", msgs[0])

    def test_ffmpeg_without_drawtext_names_the_full_build(self):
        with mock.patch("check._filters", return_value={"blurdetect", "signalstats", "tile", "drawbox"}):
            msgs = check.problems()
        self.assertEqual(len(msgs), 1)
        self.assertIn("drawtext", msgs[0])
        self.assertIn("ffmpeg-full", msgs[0])

    def test_keg_only_ffmpeg_full_goes_first_on_path(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"PATH": "/usr/bin:/bin"}
            with mock.patch.dict(os.environ, env, clear=True):
                common.prefer_full_ffmpeg([d, "/nope/bin"])
                self.assertEqual(os.environ["PATH"], f"{d}:/usr/bin:/bin")
                common.prefer_full_ffmpeg([d])  # idempotent
                self.assertEqual(os.environ["PATH"], f"{d}:/usr/bin:/bin")


class CapCutReadinessTests(unittest.TestCase):
    def test_not_installed(self):
        with mock.patch("capcut.capcut_version", return_value=None):
            self.assertIn("not installed", capcut.draft_problem("/nope"))

    def test_never_opened(self):
        with tempfile.TemporaryDirectory() as d, mock.patch("capcut.capcut_version", return_value="9.6.0"):
            self.assertIn("open CapCut once", capcut.draft_problem(os.path.join(d, "missing")))

    def test_ready(self):
        with tempfile.TemporaryDirectory() as d, mock.patch("capcut.capcut_version", return_value="9.6.0"), \
                mock.patch("capcut.capcut_running", return_value=False):
            open(os.path.join(d, "root_meta_info.json"), "w").write("{}")
            self.assertIsNone(capcut.draft_problem(d))

    def test_running(self):
        with tempfile.TemporaryDirectory() as d, mock.patch("capcut.capcut_version", return_value="9.6.0"), \
                mock.patch("capcut.capcut_running", return_value=True):
            open(os.path.join(d, "root_meta_info.json"), "w").write("{}")
            self.assertIn("Cmd+Q", capcut.draft_problem(d))


if __name__ == "__main__":
    unittest.main()
