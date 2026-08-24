"""Per-analysis ownership tokens.

On analysis creation the API returns a high-entropy owner token (once). Only its
SHA-256 hash is stored, and access to the analysis requires presenting the token
(via the ``X-Owner-Token`` header) when enforcement is enabled. This gives
lightweight ownership isolation without accounts or a database.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

OWNER_TOKEN_HEADER = "X-Owner-Token"


def new_owner_token() -> str:
    return secrets.token_urlsafe(32)


def hash_owner_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_owner_token(token: str, token_hash: str) -> bool:
    if not token or not token_hash:
        return False
    return hmac.compare_digest(hash_owner_token(token), token_hash)
