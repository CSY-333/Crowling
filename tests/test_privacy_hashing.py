from src.privacy.hashing import PrivacyHasher


def test_hash_identifier_is_deterministic():
    hasher = PrivacyHasher("run-salt")

    value = hasher.hash_identifier("author123")
    assert value == hasher.hash_identifier("author123")
    assert value != hasher.hash_identifier("AUTHOR123")


def test_hash_identifier_handles_empty_values():
    hasher = PrivacyHasher("salt")
    assert hasher.hash_identifier(None) is None
    assert hasher.hash_identifier("") is None
