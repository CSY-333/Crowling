import secrets
from typing import Tuple

from ..config import PrivacyConfig
from .hashing import PrivacyHasher


def build_privacy_hasher(config: PrivacyConfig, run_id: str) -> Tuple[PrivacyHasher, str]:
    """
    Create a PrivacyHasher according to the configured mode.
    Returns the hasher and the salt that was used (not persisted).
    """
    if config.mode == "ephemeral":
        salt = secrets.token_hex(32)
    elif config.mode == "longitudinal":
        if not config.fixed_salt:
            raise ValueError("privacy.fixed_salt must be provided when privacy.mode='longitudinal'.")
        salt = config.fixed_salt
    else:
        raise ValueError(f"Unsupported privacy mode: {config.mode}")

    # Use run_id as entropy fallback if salt somehow empty (should not happen).
    if not salt:
        salt = f"{run_id}-{secrets.token_hex(16)}"
    return PrivacyHasher(salt), salt
