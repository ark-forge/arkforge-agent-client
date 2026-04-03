"""Exceptions for the ArkForge SDK."""


class ArkForgeError(Exception):
    """Base exception for all SDK errors."""


class AuthError(ArkForgeError):
    """API key missing or invalid."""


class APIError(ArkForgeError):
    """Unexpected HTTP error from the Trust Layer."""

    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}" if detail else f"HTTP {status_code}")


class ProofError(ArkForgeError):
    """Proof verification or generation failed."""


class InsufficientCreditsError(ArkForgeError):
    """Not enough prepaid credits to complete the operation."""
