import hashlib
import hmac
from typing import Optional

class PrivacyHasher:
    def __init__(self, salt: str):
        self.salt = salt.encode('utf-8')

    def hash_identifier(self, identifier: Optional[str]) -> Optional[str]:
        """
        Return SHA-256 HMAC of identifier using run salt.
        Safe against rainbow tables.
        Returns None if input is None/Empty.
        """
        if not identifier:
            return None
            
        return hmac.new(
            self.salt, 
            identifier.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
