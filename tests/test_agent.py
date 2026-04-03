"""Unit tests for ArkForge agent client.

Tests cover pure logic (no network calls). HTTP calls are mocked via
unittest.mock so tests run offline and are deterministic.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.headers = {}
    return resp


def _proof_body(proof_id: str = "prf_test_001") -> dict:
    return {
        "proof": {
            "proof_id": proof_id,
            "spec_version": "2.0",
            "hashes": {
                "chain": "sha256:abc123def456",
                "request": "sha256:req123",
                "response": "sha256:resp456",
            },
            "certification_fee": {
                "amount": 0.10,
                "currency": "eur",
                "status": "succeeded",
                "method": "credits",
                "transaction_id": "crd_test_001",
            },
            "timestamp": "2026-03-03T12:00:00+00:00",
            "arkforge_signature": "ed25519:signaturehere",
            "verification_url": f"https://trust.arkforge.tech/v1/proof/{proof_id}",
        },
        "service_response": {"status_code": 200, "body": {}},
    }


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

class TestConfig:

    def test_get_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_abc123")
        assert agent._get_api_key() == "mcp_test_abc123"

    def test_get_api_key_fallback(self, monkeypatch):
        monkeypatch.delenv("TRUST_LAYER_API_KEY", raising=False)
        monkeypatch.setenv("ARKFORGE_SCAN_API_KEY", "mcp_test_fallback")
        assert agent._get_api_key() == "mcp_test_fallback"

    def test_get_api_key_empty(self, monkeypatch):
        monkeypatch.delenv("TRUST_LAYER_API_KEY", raising=False)
        monkeypatch.delenv("ARKFORGE_SCAN_API_KEY", raising=False)
        assert agent._get_api_key() == ""

    def test_scan_provider_price_default(self, monkeypatch):
        monkeypatch.delenv("SCAN_PROVIDER_PRICE", raising=False)
        assert agent._get_scan_provider_price() == 100

    def test_scan_provider_price_custom(self, monkeypatch):
        monkeypatch.setenv("SCAN_PROVIDER_PRICE", "250")
        assert agent._get_scan_provider_price() == 250

    def test_scan_provider_price_invalid(self, monkeypatch):
        monkeypatch.setenv("SCAN_PROVIDER_PRICE", "notanumber")
        assert agent._get_scan_provider_price() == 100


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

class TestSafeJson:

    def test_valid_json(self):
        resp = MagicMock()
        resp.json.return_value = {"key": "value"}
        resp.status_code = 200
        assert agent._safe_json(resp) == {"key": "value"}

    def test_invalid_json(self):
        import requests
        resp = MagicMock()
        resp.json.side_effect = requests.exceptions.JSONDecodeError("err", "", 0)
        resp.status_code = 500
        resp.text = "not json"
        result = agent._safe_json(resp)
        assert "error" in result
        assert "500" in result["error"]


class TestErrorResult:

    def test_http_error_with_detail(self):
        # body.get("error") takes priority over body.get("detail")
        resp = _mock_response(400, {"error": "bad_request", "detail": "Missing field"})
        result = agent._error_result(resp)
        assert result["error"] == "HTTP 400"
        assert result.get("detail") == "bad_request"

    def test_http_error_detail_only(self):
        # when no "error" key, "detail" value is used
        resp = _mock_response(422, {"detail": "Missing field x"})
        result = agent._error_result(resp)
        assert result["error"] == "HTTP 422"
        assert "Missing field x" in result.get("detail", "")

    def test_http_error_bubbles_proof(self):
        proof = {"proof_id": "prf_001"}
        resp = _mock_response(402, {"error": "no_credits", "proof": proof})
        result = agent._error_result(resp)
        assert result["proof"] == proof

    def test_non_json_response(self):
        import requests
        resp = MagicMock()
        resp.status_code = 503
        resp.json.side_effect = requests.exceptions.JSONDecodeError("err", "", 0)
        resp.text = "Service Unavailable"
        result = agent._error_result(resp)
        assert result["error"] == "HTTP 503"


# ---------------------------------------------------------------------------
# API functions (mocked HTTP)
# ---------------------------------------------------------------------------

class TestScanRepo:

    def test_scan_success(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        body = _proof_body("prf_scan_001")
        with patch("requests.post", return_value=_mock_response(200, body)):
            result = agent.scan_repo("https://github.com/owner/repo")
        assert "proof" in result
        assert result["proof"]["proof_id"] == "prf_scan_001"

    def test_scan_no_api_key(self, monkeypatch):
        monkeypatch.delenv("TRUST_LAYER_API_KEY", raising=False)
        monkeypatch.delenv("ARKFORGE_SCAN_API_KEY", raising=False)
        result = agent.scan_repo("https://github.com/owner/repo")
        assert "error" in result
        assert "TRUST_LAYER_API_KEY" in result["error"]

    def test_scan_server_error(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        resp = _mock_response(500, {"error": "internal", "detail": "Server error"})
        with patch("requests.post", return_value=resp):
            result = agent.scan_repo("https://github.com/owner/repo")
        assert "error" in result


class TestVerifyProof:

    def test_verify_success(self):
        body = {"proof_id": "prf_001", "hashes": {}, "verified": True}
        with patch("requests.get", return_value=_mock_response(200, body)):
            result = agent.verify_proof("prf_001")
        assert result["proof_id"] == "prf_001"

    def test_verify_not_found(self):
        resp = _mock_response(404, {"error": "not_found"})
        with patch("requests.get", return_value=resp):
            result = agent.verify_proof("prf_nonexistent")
        assert "error" in result


class TestGetReputation:

    def test_reputation_success(self):
        body = {
            "agent_id": "sha256:abc123",
            "reputation_score": 85,
            "scoring": {
                "success_rate": 100.0,
                "confidence": 0.85,
                "formula": "floor(success_rate × confidence) − penalties",
            },
            "total_proofs": 10,
            "signature": "ed25519:sig",
        }
        with patch("requests.get", return_value=_mock_response(200, body)):
            result = agent.get_reputation("sha256:abc123")
        assert result["reputation_score"] == 85
        assert result["scoring"]["confidence"] == 0.85

    def test_reputation_unknown_agent(self):
        resp = _mock_response(404, {"error": "agent_not_found"})
        with patch("requests.get", return_value=resp):
            result = agent.get_reputation("sha256:unknown")
        assert "error" in result


class TestBuyCredits:

    def test_buy_credits_success(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        body = {"credits_added": 1.0, "balance": 1.0, "proofs_available": 10}
        with patch("requests.post", return_value=_mock_response(200, body)):
            result = agent.buy_credits(1.0)
        assert result["credits_added"] == 1.0

    def test_buy_credits_no_api_key(self, monkeypatch):
        monkeypatch.delenv("TRUST_LAYER_API_KEY", raising=False)
        monkeypatch.delenv("ARKFORGE_SCAN_API_KEY", raising=False)
        result = agent.buy_credits(1.0)
        assert "error" in result


# ---------------------------------------------------------------------------
# CLI argument helpers
# ---------------------------------------------------------------------------

class TestComplianceReport:

    def _report_body(self, framework: str = "eu_ai_act") -> dict:
        return {
            "report_id": "rpt_20260403_120000_abc123",
            "framework": framework,
            "framework_version": "1.0",
            "date_range": {"from": "2026-01-01T00:00:00+00:00", "to": "2026-03-31T00:00:00+00:00"},
            "proof_count": 5,
            "articles": [
                {"article": "Art. 9" if framework == "eu_ai_act" else "§ 6.1",
                 "title": "Risk Management System" if framework == "eu_ai_act" else "Risk and Opportunity Management",
                 "status": "covered", "evidence": "Chain hash present", "proof_count": 5},
            ],
            "gaps": [],
            "summary": {"covered": 5, "partial": 0, "gap": 0, "not_applicable": 1},
        }

    def test_compliance_eu_ai_act_success(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        body = self._report_body("eu_ai_act")
        with patch("requests.post", return_value=_mock_response(200, body)):
            result = agent.compliance_report("2026-01-01", "2026-03-31", framework="eu_ai_act")
        assert result["framework"] == "eu_ai_act"
        assert result["report_id"].startswith("rpt_")
        assert "articles" in result

    def test_compliance_iso_42001_success(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        body = self._report_body("iso_42001")
        with patch("requests.post", return_value=_mock_response(200, body)):
            result = agent.compliance_report("2026-01-01", "2026-03-31", framework="iso_42001")
        assert result["framework"] == "iso_42001"
        assert result["proof_count"] == 5

    def test_compliance_default_framework_is_eu_ai_act(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        captured = {}

        def mock_post(url, headers=None, json=None, timeout=None):
            captured["body"] = json
            return _mock_response(200, self._report_body("eu_ai_act"))

        with patch("requests.post", side_effect=mock_post):
            agent.compliance_report("2026-01-01", "2026-03-31")

        assert captured["body"]["framework"] == "eu_ai_act"

    def test_compliance_framework_passed_to_server(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        captured = {}

        def mock_post(url, headers=None, json=None, timeout=None):
            captured["body"] = json
            return _mock_response(200, self._report_body("iso_42001"))

        with patch("requests.post", side_effect=mock_post):
            agent.compliance_report("2026-01-01", "2026-03-31", framework="iso_42001")

        assert captured["body"]["framework"] == "iso_42001"
        assert captured["body"]["date_from"] == "2026-01-01"
        assert captured["body"]["date_to"] == "2026-03-31"

    def test_compliance_no_api_key(self, monkeypatch):
        monkeypatch.delenv("TRUST_LAYER_API_KEY", raising=False)
        monkeypatch.delenv("ARKFORGE_SCAN_API_KEY", raising=False)
        result = agent.compliance_report("2026-01-01", "2026-03-31")
        assert "error" in result
        assert "TRUST_LAYER_API_KEY" in result["error"]

    def test_compliance_unknown_framework_error(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        body = {"error": {"code": "unknown_framework",
                          "message": "Unknown framework 'bad_fw'. Available: eu_ai_act, iso_42001",
                          "status": 400}}
        with patch("requests.post", return_value=_mock_response(400, body)):
            result = agent.compliance_report("2026-01-01", "2026-03-31", framework="bad_fw")
        assert "error" in result

    def test_compliance_server_error(self, monkeypatch):
        monkeypatch.setenv("TRUST_LAYER_API_KEY", "mcp_test_key")
        with patch("requests.post", return_value=_mock_response(500, {"error": "internal"})):
            result = agent.compliance_report("2026-01-01", "2026-03-31")
        assert "error" in result


class TestExtractReceiptUrl:

    def test_extract_flag(self):
        args = ["scan", "https://github.com/x/y", "--receipt-url", "https://pay.stripe.com/abc"]
        assert agent._extract_receipt_url(args) == "https://pay.stripe.com/abc"

    def test_extract_equals(self):
        args = ["scan", "https://github.com/x/y", "--receipt-url=https://pay.stripe.com/abc"]
        assert agent._extract_receipt_url(args) == "https://pay.stripe.com/abc"

    def test_extract_missing(self):
        args = ["scan", "https://github.com/x/y"]
        assert agent._extract_receipt_url(args) == ""

    def test_extract_flag_at_end_without_value(self):
        args = ["scan", "https://github.com/x/y", "--receipt-url"]
        assert agent._extract_receipt_url(args) == ""
