import unittest


class TestConfig(unittest.TestCase):
    def test_settings_load(self):
        try:
            from src.core.config import Settings
            settings = Settings()
            self.assertEqual(settings.gemini_model, "gemini-3.8-flash")
            self.assertEqual(settings.bot_username, "smartbujetbot")
        except ImportError:
            self.skipTest("pydantic or sqlalchemy not installed in current environment")


if __name__ == "__main__":
    unittest.main()
