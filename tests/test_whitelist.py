import unittest
from unittest.mock import MagicMock
from app.service.cache_service import CacheService
from app.config.settings import Settings


class TestWhitelistLogic(unittest.TestCase):
    def setUp(self):
        self.settings = MagicMock(spec=Settings)
        self.cache_repo = MagicMock()
        self.github_repo = MagicMock()
        self.service = CacheService(self.settings, self.cache_repo, self.github_repo)

    def test_is_whitelisted_empty_list(self):
        """If repositories list is empty, all repositories should be whitelisted."""
        self.settings.repositories = []
        self.assertTrue(self.service._is_whitelisted("owner", "repo"))

    def test_is_whitelisted_exact_match(self):
        """Should match owner/repo exactly."""
        self.settings.repositories = ["owner/repo"]
        self.assertTrue(self.service._is_whitelisted("owner", "repo"))
        self.assertFalse(self.service._is_whitelisted("other", "repo"))

    def test_is_whitelisted_substring_match(self):
        """Should match if target is a substring of whitelisted item (e.g. within URL)."""
        self.settings.repositories = ["https://github.com/owner/repo"]
        self.assertTrue(self.service._is_whitelisted("owner", "repo"))

    def test_is_whitelisted_case_insensitive(self):
        """Matches should be case-insensitive."""
        self.settings.repositories = ["OWNER/REPO"]
        self.assertTrue(self.service._is_whitelisted("owner", "repo"))
        self.assertTrue(self.service._is_whitelisted("OWNER", "REPO"))

    def test_is_whitelisted_multiple_items(self):
        """Should match any item in the comma-separated list."""
        self.settings.repositories = ["other/repo", "owner/repo"]
        self.assertTrue(self.service._is_whitelisted("owner", "repo"))
        self.assertTrue(self.service._is_whitelisted("other", "repo"))
        self.assertFalse(self.service._is_whitelisted("third", "repo"))

    def test_is_whitelisted_organization_match(self):
        """Should match if only organization/owner is specified and it matches the substring."""
        self.settings.repositories = ["litestar-org"]
        self.assertTrue(self.service._is_whitelisted("litestar-org", "litestar"))
        self.assertFalse(self.service._is_whitelisted("other-org", "litestar"))


if __name__ == "__main__":
    unittest.main()
