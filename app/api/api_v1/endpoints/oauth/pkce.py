from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Optional


def verify_pkce(
    code_challenge: Optional[str],
    code_verifier: Optional[str],
    method: Optional[str],
) -> bool:
    """Verify PKCE code challenge."""
    if not code_challenge or not code_verifier:
        return False

    if method == "S256":
        hash_obj = hashlib.sha256(code_verifier.encode("ascii")).digest()
        encoded = base64.urlsafe_b64encode(hash_obj).decode("ascii").rstrip("=")
        return secrets.compare_digest(encoded, code_challenge)
    if method == "plain":
        return secrets.compare_digest(code_verifier, code_challenge)

    return False
