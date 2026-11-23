import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import make_setup_link as msl  # noqa: E402


class SetupLinkTests(unittest.TestCase):
    def test_repo_from_remote(self):
        self.assertEqual(msl.repo_from_remote("https://github.com/mruth1022/nursing-flashcards.git\n"), "mruth1022/nursing-flashcards")
        self.assertEqual(msl.repo_from_remote("git@github.com:mruth1022/nursing-flashcards.git"), "mruth1022/nursing-flashcards")
        self.assertIsNone(msl.repo_from_remote("https://gitlab.com/a/b.git"))

    def test_site_and_link(self):
        self.assertEqual(msl.site_for("MRuth1022/nursing-flashcards"), "https://mruth1022.github.io/nursing-flashcards/")
        self.assertEqual(msl.build_link("https://o.github.io/r/", "github_pat_AB_c"), "https://o.github.io/r/#setup=github_pat_AB_c")

    def test_token_shape(self):
        self.assertTrue(msl.looks_like_token("github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz"))
        self.assertTrue(msl.looks_like_token("ghp_abcdefghijklmnopqrstuvwxyz0123"))
        self.assertFalse(msl.looks_like_token("hello world"))
        self.assertFalse(msl.looks_like_token("github_pat_short"))


if __name__ == "__main__":
    unittest.main()
