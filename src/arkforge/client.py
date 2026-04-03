"""ArkForge Trust Layer client."""

import os
from typing import Optional

import requests

from .errors import APIError, AuthError
from .version import __version__

_AGENT_IDENTITY = "arkforge-python-sdk"
_DEFAULT_BASE_URL = "https://trust.arkforge.tech"
_DEFAULT_SCAN_URL = "https://arkforge.tech/api/v1/scan-repo"
_TIMEOUT = 130


class TrustLayerClient:
    """Client for the ArkForge Trust Layer API.

    Certifies every API call with a tamper-proof proof chain:
    SHA-256 hash chain + Ed25519 signature + RFC 3161 timestamp + Sigstore Rekor.

    Args:
        api_key: Your ArkForge API key (``mcp_free_*`` or ``mcp_pro_*``).
                 Falls back to ``TRUST_LAYER_API_KEY`` env var if omitted.
        base_url: Trust Layer base URL. Defaults to ``https://trust.arkforge.tech``.
        scan_url: EU AI Act scan endpoint. Defaults to the ArkForge hosted scanner.
        timeout:  Request timeout in seconds (default: 130).

    Example::

        from arkforge import TrustLayerClient

        client = TrustLayerClient(api_key="mcp_pro_...")
        proof = client.scan_repo("https://github.com/org/repo")
        print(proof["proof"]["proof_id"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = _DEFAULT_BASE_URL,
        scan_url: str = _DEFAULT_SCAN_URL,
        timeout: int = _TIMEOUT,
    ):
        self._api_key = api_key or os.environ.get("TRUST_LAYER_API_KEY", "").strip()
        self._base_url = base_url.rstrip("/")
        self._scan_url = scan_url
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        if not self._api_key:
            raise AuthError("API key not set. Pass api_key= or set TRUST_LAYER_API_KEY.")
        return {
            "X-Api-Key": self._api_key,
            "Content-Type": "application/json",
            "X-Agent-Identity": _AGENT_IDENTITY,
            "X-Agent-Version": __version__,
        }

    def _parse(self, resp: requests.Response) -> dict:
        """Parse response, raise APIError on non-2xx."""
        if resp.status_code not in (200, 201):
            try:
                body = resp.json()
                detail = body.get("detail") or body.get("error") or ""
                if isinstance(detail, dict):
                    detail = detail.get("message", str(detail))
            except Exception:
                detail = resp.text[:300]
            raise APIError(resp.status_code, str(detail))
        try:
            result = resp.json()
        except Exception:
            raise APIError(resp.status_code, "Invalid JSON response")
        # Capture Ghost Stamp headers
        ghost = {k: v for k, v in resp.headers.items() if k.startswith("X-ArkForge-")}
        if ghost:
            result["_response_headers"] = ghost
        return result

    def _proxy(self, target: str, payload: dict, description: str = "",
               method: str = "POST", receipt_url: str = "") -> dict:
        """Route a call through the Trust Layer proxy."""
        body: dict = {
            "target": target,
            "payload": payload,
            "method": method,
            "description": description,
        }
        if receipt_url:
            body["provider_payment"] = {"type": "stripe", "receipt_url": receipt_url}
        resp = requests.post(
            f"{self._base_url}/v1/proxy",
            headers=self._headers(),
            json=body,
            timeout=self._timeout,
        )
        return self._parse(resp)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_repo(self, repo_url: str, receipt_url: str = "") -> dict:
        """Scan a repository for EU AI Act compliance.

        Costs 0.10 EUR from prepaid credits. Routes through the Trust Layer
        proxy — the proof certifies both the request and the scan result.

        Args:
            repo_url:    Public repository URL (GitHub, GitLab, etc.).
            receipt_url: Optional Stripe receipt URL for Mode B (direct
                         provider payment evidence).

        Returns:
            Trust Layer response with ``proof`` and ``service_response`` keys.
        """
        return self._proxy(
            target=self._scan_url,
            payload={"repo_url": repo_url},
            description=f"EU AI Act compliance scan: {repo_url}",
            receipt_url=receipt_url,
        )

    def pay(self, receipt_url: str = "") -> dict:
        """Generate a payment proof without an upstream call (0.10 EUR).

        Useful for testing the Trust Layer flow or generating a standalone
        payment certification.

        Returns:
            Trust Layer response with ``proof`` key.
        """
        return self._proxy(
            target=f"{self._base_url}/v1/pricing",
            payload={},
            description="Agent payment proof",
            method="GET",
            receipt_url=receipt_url,
        )

    def buy_credits(self, amount: float) -> dict:
        """Buy prepaid credits (charges your saved Stripe card).

        Args:
            amount: Amount in EUR (min 1.00, max 100.00).

        Returns:
            dict with ``credits_added``, ``balance``, ``proofs_available``,
            and ``receipt_url`` keys.
        """
        resp = requests.post(
            f"{self._base_url}/v1/credits/buy",
            headers=self._headers(),
            json={"amount": amount},
            timeout=self._timeout,
        )
        return self._parse(resp)

    def verify_proof(self, proof_id: str) -> dict:
        """Verify an existing proof by ID (no API key required).

        Args:
            proof_id: The proof ID returned by a previous Trust Layer call.

        Returns:
            Full proof record with hash chain, signature, and timestamp data.
        """
        resp = requests.get(
            f"{self._base_url}/v1/proof/{proof_id}",
            timeout=30,
        )
        return self._parse(resp)

    def get_reputation(self, agent_id: str) -> dict:
        """Get the public reputation score for an agent (0–100).

        Args:
            agent_id: Agent identifier (e.g. ``"arkforge-agent-client"``).

        Returns:
            dict with ``reputation_score``, ``scoring``, and ``total_proofs``.
        """
        resp = requests.get(
            f"{self._base_url}/v1/agent/{agent_id}/reputation",
            timeout=30,
        )
        return self._parse(resp)

    def file_dispute(self, proof_id: str, reason: str) -> dict:
        """File a dispute against a proof.

        Args:
            proof_id: The proof ID to dispute.
            reason:   Dispute reason (required, non-empty).

        Returns:
            dict with ``dispute_id``, ``status``, and ``resolution``.
        """
        resp = requests.post(
            f"{self._base_url}/v1/disputes",
            headers=self._headers(),
            json={"proof_id": proof_id, "reason": reason},
            timeout=30,
        )
        return self._parse(resp)

    def get_disputes(self, agent_id: str) -> dict:
        """Get dispute history for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            dict with ``disputes`` list and ``summary`` (total, won, lost).
        """
        resp = requests.get(
            f"{self._base_url}/v1/agent/{agent_id}/disputes",
            timeout=30,
        )
        return self._parse(resp)

    def assess_mcp(self, server_id: str, tools: list, server_version: str = "") -> dict:
        """Assess an MCP server manifest for security posture.

        Analyzes tool capabilities for dangerous patterns (filesystem write,
        code execution, env access, network), detects drift from the previous
        baseline, and tracks version changes.

        Args:
            server_id:      Stable identifier for this MCP server.
            tools:          List of tool dicts with at minimum a ``"name"`` field.
                            Optional: ``"description"``, ``"inputSchema"``, ``"version"``.
            server_version: Optional server version string (e.g. ``"1.2.0"``).

        Returns:
            dict with ``assess_id``, ``risk_score`` (0–100), ``findings``,
            ``drift_detected``, and ``baseline_status``.
        """
        body: dict = {"server_id": server_id, "manifest": {"tools": tools}}
        if server_version:
            body["server_version"] = server_version
        resp = requests.post(
            f"{self._base_url}/v1/assess",
            headers=self._headers(),
            json=body,
            timeout=30,
        )
        return self._parse(resp)

    def compliance_report(
        self,
        date_from: str,
        date_to: str,
        framework: str = "eu_ai_act",
    ) -> dict:
        """Generate a compliance report for all proofs in a date range.

        Aggregates proofs certified under this API key and maps them to
        the requested compliance framework's articles.

        Args:
            date_from: ISO 8601 start date (e.g. ``"2026-01-01"``).
            date_to:   ISO 8601 end date (e.g. ``"2026-12-31"``).
            framework: Compliance framework. Supported: ``"eu_ai_act"``,
                       ``"iso_42001"``.

        Returns:
            dict with ``report_id``, ``framework``, ``proof_count``,
            ``articles``, ``gaps``, and ``summary``.
        """
        resp = requests.post(
            f"{self._base_url}/v1/compliance-report",
            headers=self._headers(),
            json={"framework": framework, "date_from": date_from, "date_to": date_to},
            timeout=60,
        )
        return self._parse(resp)
