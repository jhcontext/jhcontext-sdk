"""Tests for SQLitePIIVault storage backend."""

import os
import tempfile

import pytest

from jhcontext.server.storage.pii_vault import SQLitePIIVault


@pytest.fixture
def vault(tmp_path):
    db_path = str(tmp_path / "test_pii_vault.db")
    v = SQLitePIIVault(db_path=db_path)
    yield v
    v.close()


class TestSQLitePIIVault:
    def test_store_and_retrieve(self, vault):
        vault.store("pii:tok-abc123", "ctx-1", "alice@example.com", "[0].subject")
        assert vault.retrieve("pii:tok-abc123") == "alice@example.com"

    def test_retrieve_nonexistent(self, vault):
        assert vault.retrieve("pii:tok-doesnotexist") is None

    def test_retrieve_by_context(self, vault):
        vault.store("pii:tok-aaa", "ctx-1", "alice@example.com", "[0].subject")
        vault.store("pii:tok-bbb", "ctx-1", "+1-555-1234", "[0].phone")
        vault.store("pii:tok-ccc", "ctx-2", "bob@example.com", "[0].subject")

        tokens = vault.retrieve_by_context("ctx-1")
        assert len(tokens) == 2
        assert {t["token_id"] for t in tokens} == {"pii:tok-aaa", "pii:tok-bbb"}

    def test_purge_by_context(self, vault):
        vault.store("pii:tok-aaa", "ctx-1", "alice@example.com", "[0].subject")
        vault.store("pii:tok-bbb", "ctx-1", "+1-555-1234", "[0].phone")

        deleted = vault.purge_by_context("ctx-1")
        assert deleted == 2
        assert vault.retrieve("pii:tok-aaa") is None
        assert vault.retrieve("pii:tok-bbb") is None

    def test_purge_by_context_isolated(self, vault):
        """Purging one context should not affect others."""
        vault.store("pii:tok-aaa", "ctx-1", "alice@example.com", "[0].subject")
        vault.store("pii:tok-bbb", "ctx-2", "bob@example.com", "[0].subject")

        vault.purge_by_context("ctx-1")

        assert vault.retrieve("pii:tok-aaa") is None
        assert vault.retrieve("pii:tok-bbb") == "bob@example.com"

    def test_purge_by_context_returns_zero_for_empty(self, vault):
        deleted = vault.purge_by_context("ctx-nonexistent")
        assert deleted == 0

    def test_purge_expired(self, vault):
        # Store with a known old timestamp
        vault._conn.execute(
            "INSERT INTO pii_tokens (token_id, context_id, field_path, original_value, created_at) VALUES (?, ?, ?, ?, ?)",
            ("pii:tok-old", "ctx-1", "[0].subject", "old@example.com", "2020-01-01T00:00:00+00:00"),
        )
        vault._conn.execute(
            "INSERT INTO pii_tokens (token_id, context_id, field_path, original_value, created_at) VALUES (?, ?, ?, ?, ?)",
            ("pii:tok-new", "ctx-2", "[0].subject", "new@example.com", "2099-01-01T00:00:00+00:00"),
        )
        vault._conn.commit()

        deleted = vault.purge_expired("2025-01-01T00:00:00+00:00")
        assert deleted == 1
        assert vault.retrieve("pii:tok-old") is None
        assert vault.retrieve("pii:tok-new") == "new@example.com"

    def test_store_upsert(self, vault):
        """Storing the same token_id again should update the value."""
        vault.store("pii:tok-aaa", "ctx-1", "alice@example.com", "[0].subject")
        vault.store("pii:tok-aaa", "ctx-1", "alice_updated@example.com", "[0].subject")
        assert vault.retrieve("pii:tok-aaa") == "alice_updated@example.com"

    def test_separate_db_file(self, tmp_path):
        """PII vault uses a separate database file from main storage."""
        vault_path = str(tmp_path / "pii_vault.db")
        main_path = str(tmp_path / "data.db")

        v = SQLitePIIVault(db_path=vault_path)
        v.store("pii:tok-aaa", "ctx-1", "alice@example.com", "[0].subject")
        v.close()

        assert os.path.exists(vault_path)
        assert not os.path.exists(main_path)
