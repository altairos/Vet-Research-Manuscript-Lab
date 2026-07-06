"""Tests for Settings configuration and pool config derivation."""

from __future__ import annotations

import unittest
from unittest import mock

from vet_manuscript_lab.config import Settings
from vet_manuscript_lab.infrastructure.database.backends import PoolConfig


class SettingsDatabaseUrlTests(unittest.TestCase):
    """``is_sqlite`` and ``is_postgres`` detect the URL scheme."""

    def test_sqlite_url_detected(self) -> None:
        settings = Settings(
            environment="development",
            database_url="sqlite:///./test.db",
            artifact_root=__import__("pathlib").Path("./artifacts"),
            checkpoint_path=__import__("pathlib").Path("./artifacts/cp.sqlite"),
            zotero_api_key="",
            zotero_library_id="",
            zotero_library_type="user",
            db_pool_size=5,
            db_max_overflow=10,
            db_pool_recycle=1800,
        )
        self.assertTrue(settings.is_sqlite)
        self.assertFalse(settings.is_postgres)

    def test_postgresql_url_detected(self) -> None:
        settings = Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost:5432/vet_lab",
            artifact_root=__import__("pathlib").Path("./artifacts"),
            checkpoint_path=__import__("pathlib").Path("./artifacts/cp.sqlite"),
            zotero_api_key="",
            zotero_library_id="",
            zotero_library_type="user",
            db_pool_size=5,
            db_max_overflow=10,
            db_pool_recycle=1800,
        )
        self.assertTrue(settings.is_postgres)
        self.assertFalse(settings.is_sqlite)

    def test_psycopg_scheme_detected_as_postgres(self) -> None:
        settings = Settings(
            environment="production",
            database_url="postgresql+psycopg://user:pass@localhost:5432/vet_lab",
            artifact_root=__import__("pathlib").Path("./artifacts"),
            checkpoint_path=__import__("pathlib").Path("./artifacts/cp.sqlite"),
            zotero_api_key="",
            zotero_library_id="",
            zotero_library_type="user",
            db_pool_size=5,
            db_max_overflow=10,
            db_pool_recycle=1800,
        )
        self.assertTrue(settings.is_postgres)


class SettingsPoolConfigTests(unittest.TestCase):
    """``pool_config`` builds a ``PoolConfig`` from settings fields."""

    def test_default_pool_config(self) -> None:
        settings = Settings(
            environment="development",
            database_url="sqlite:///./test.db",
            artifact_root=__import__("pathlib").Path("./artifacts"),
            checkpoint_path=__import__("pathlib").Path("./artifacts/cp.sqlite"),
            zotero_api_key="",
            zotero_library_id="",
            zotero_library_type="user",
            db_pool_size=5,
            db_max_overflow=10,
            db_pool_recycle=1800,
        )
        config = settings.pool_config
        self.assertIsInstance(config, PoolConfig)
        self.assertEqual(config.pool_size, 5)
        self.assertEqual(config.max_overflow, 10)
        self.assertEqual(config.pool_recycle, 1800)
        self.assertTrue(config.pool_pre_ping)

    def test_custom_pool_config(self) -> None:
        settings = Settings(
            environment="production",
            database_url="postgresql://localhost/db",
            artifact_root=__import__("pathlib").Path("./artifacts"),
            checkpoint_path=__import__("pathlib").Path("./artifacts/cp.sqlite"),
            zotero_api_key="",
            zotero_library_id="",
            zotero_library_type="user",
            db_pool_size=20,
            db_max_overflow=5,
            db_pool_recycle=300,
        )
        config = settings.pool_config
        self.assertEqual(config.pool_size, 20)
        self.assertEqual(config.max_overflow, 5)
        self.assertEqual(config.pool_recycle, 300)


class SettingsFromEnvTests(unittest.TestCase):
    """``from_env`` reads pool parameters from environment variables."""

    def test_from_env_defaults(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {},
            clear=False,
        ):
            # Remove any test env vars
            import os

            for key in [
                "VET_LAB_DB_POOL_SIZE",
                "VET_LAB_DB_MAX_OVERFLOW",
                "VET_LAB_DB_POOL_RECYCLE",
            ]:
                os.environ.pop(key, None)

            settings = Settings.from_env()
            self.assertEqual(settings.db_pool_size, 5)
            self.assertEqual(settings.db_max_overflow, 10)
            self.assertEqual(settings.db_pool_recycle, 1800)

    def test_from_env_overrides(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {
                "VET_LAB_DB_POOL_SIZE": "15",
                "VET_LAB_DB_MAX_OVERFLOW": "20",
                "VET_LAB_DB_POOL_RECYCLE": "900",
            },
        ):
            settings = Settings.from_env()
            self.assertEqual(settings.db_pool_size, 15)
            self.assertEqual(settings.db_max_overflow, 20)
            self.assertEqual(settings.db_pool_recycle, 900)


class PoolConfigDefaultsTests(unittest.TestCase):
    """``PoolConfig`` default values are sensible for production use."""

    def test_pool_config_defaults(self) -> None:
        config = PoolConfig()
        self.assertEqual(config.pool_size, 5)
        self.assertEqual(config.max_overflow, 10)
        self.assertEqual(config.pool_recycle, 1800)
        self.assertTrue(config.pool_pre_ping)


if __name__ == "__main__":
    unittest.main()
