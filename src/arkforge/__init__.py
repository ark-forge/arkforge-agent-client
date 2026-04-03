"""ArkForge Python SDK — Trust Layer client.

Certifies every AI agent API call with a tamper-proof proof chain:
SHA-256 hash chain + Ed25519 signature + RFC 3161 timestamp + Sigstore Rekor.

Quick start::

    from arkforge import TrustLayerClient

    client = TrustLayerClient(api_key="mcp_pro_...")
    proof = client.scan_repo("https://github.com/org/repo")
    print(proof["proof"]["proof_id"])

Free API key (no card required)::

    curl -X POST https://trust.arkforge.tech/v1/keys/free-signup \\
      -H "Content-Type: application/json" \\
      -d '{"email": "agent@example.com"}'
"""

from .client import TrustLayerClient
from .errors import APIError, ArkForgeError, AuthError, InsufficientCreditsError, ProofError
from .version import __version__

__all__ = [
    "TrustLayerClient",
    "ArkForgeError",
    "AuthError",
    "APIError",
    "ProofError",
    "InsufficientCreditsError",
    "__version__",
]
