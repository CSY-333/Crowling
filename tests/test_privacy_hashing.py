from src.config import PrivacyConfig
from src.privacy.hashing import PrivacyHasher
from src.privacy.factory import build_privacy_hasher


def test_hash_identifier_is_deterministic():
    hasher = PrivacyHasher("run-salt")

    value = hasher.hash_identifier("author123")
    assert value == hasher.hash_identifier("author123")
    assert value != hasher.hash_identifier("AUTHOR123")


def test_hash_identifier_handles_empty_values():
    hasher = PrivacyHasher("salt")
    assert hasher.hash_identifier(None) is None
    assert hasher.hash_identifier("") is None


def test_build_privacy_hasher_ephemeral_uses_random_salt(monkeypatch):
    monkeypatch.setattr("src.privacy.factory.secrets.token_hex", lambda _: "abc123")
    config = PrivacyConfig(mode="ephemeral")
    hasher, salt = build_privacy_hasher(config, run_id="run-1")
    assert salt == "abc123"
    assert hasher.hash_identifier("user") == PrivacyHasher("abc123").hash_identifier("user")


def test_build_privacy_hasher_longitudinal_requires_fixed_salt():
    config = PrivacyConfig(mode="longitudinal", fixed_salt="fixed-salt")
    hasher, salt = build_privacy_hasher(config, run_id="run-1")
    assert salt == "fixed-salt"
    assert hasher.hash_identifier("user") == PrivacyHasher("fixed-salt").hash_identifier("user")
