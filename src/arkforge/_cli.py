"""CLI entry point for the ArkForge SDK (``arkforge`` command)."""

import json
import os
import sys
from datetime import datetime, timezone

import requests

from .client import TrustLayerClient, _DEFAULT_BASE_URL
from .errors import APIError, AuthError
from .version import __version__

_DEMO_TOOLS = [
    {"name": "get_weather", "description": "Fetch current weather for a city via public API"},
    {"name": "read_file", "description": "Read any file from the local filesystem"},
    {"name": "execute_command", "description": "Execute a shell command on the host system"},
    {"name": "send_email", "description": "Send an email via the configured SMTP server"},
]

USAGE = f"""arkforge {__version__} — ArkForge Trust Layer CLI

Usage:
  arkforge scan <repo_url>               EU AI Act compliance scan (0.10 EUR)
  arkforge pay                           Payment proof only (0.10 EUR)
  arkforge credits <amount>              Buy prepaid credits (min 1 EUR)
  arkforge verify <proof_id>             Verify an existing proof
  arkforge reputation <agent_id>         Agent reputation score (0-100)
  arkforge dispute <proof_id> "reason"   File a dispute against a proof
  arkforge disputes <agent_id>           Dispute history for an agent
  arkforge assess <server_id>            Assess MCP server security posture
  arkforge assess --url <server_url>     Assess a live MCP server
  arkforge assess --demo                 Demo assessment with sample tools
  arkforge compliance                    Generate EU AI Act compliance report

Options:
  --receipt-url URL   Mode B: attach a direct provider payment receipt
  --pay-provider      Mode B: pay provider via Stripe then attach receipt

Environment:
  TRUST_LAYER_API_KEY   Your ArkForge API key (mcp_free_* or mcp_pro_*)
  TRUST_LAYER_BASE      Trust Layer URL (default: https://trust.arkforge.tech)

Get a free API key (no card required):
  curl -X POST https://trust.arkforge.tech/v1/keys/free-signup \\
    -H "Content-Type: application/json" \\
    -d '{{"email": "agent@example.com"}}'
"""


def _client() -> TrustLayerClient:
    base_url = os.environ.get("TRUST_LAYER_BASE", _DEFAULT_BASE_URL)
    return TrustLayerClient(base_url=base_url)


def _hr(title: str = ""):
    line = "=" * 60
    print(line)
    if title:
        print(title)
        print(line)


def _extract_receipt_url(args: list) -> str:
    for i, arg in enumerate(args):
        if arg == "--receipt-url" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--receipt-url="):
            return arg.split("=", 1)[1]
    return ""


def _print_proof(result: dict):
    proof = result.get("proof", {})
    if not proof:
        return
    hashes = proof.get("hashes", {})
    tsa = proof.get("timestamp_authority") or {}
    print("[PROOF]")
    print(f"  ID:           {proof.get('proof_id', 'N/A')}")
    chain = hashes.get("chain", "N/A") or "N/A"
    req_h = hashes.get("request", "N/A") or "N/A"
    print(f"  Chain hash:   {chain[:48]}...")
    print(f"  Request hash: {req_h[:48]}...")
    if proof.get("arkforge_signature"):
        print(f"  Signature:    {proof['arkforge_signature'][:20]}... (verified)")
    verify_url = proof.get("verification_url", "")
    print(f"  Verify:       {verify_url}")
    share = verify_url.replace("/v1/proof/", "/v/")
    if share != verify_url:
        print(f"  Share:        {share}")
    print(f"  Timestamp:    {proof.get('timestamp', 'N/A')}")
    if tsa.get("status"):
        print(f"  TSA:          {tsa['status']}")
    tlog = proof.get("transparency_log") or {}
    if tlog.get("status") == "verified":
        print(f"  Rekor:        verified (logIndex={tlog.get('log_index')})")
    print()


def _print_payment(result: dict):
    fee = result.get("proof", {}).get("certification_fee", {})
    if not fee:
        return
    print("[CERTIFICATION FEE]")
    print(f"  Amount: {fee.get('amount', 'N/A')} {fee.get('currency', 'EUR').upper()}")
    print(f"  Status: {fee.get('status', 'N/A')}")
    if fee.get("receipt_url"):
        print(f"  Receipt: {fee['receipt_url']}")
    print()


def _cmd_pay(args: list):
    receipt_url = _extract_receipt_url(args)
    c = _client()
    _hr("PAYMENT PROOF — 0.10 EUR")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    result = c.pay(receipt_url=receipt_url)
    _print_payment(result)
    _print_proof(result)
    _hr("DONE")


def _cmd_credits(args: list):
    if len(args) < 2:
        print("Usage: arkforge credits <amount_eur>  (min 1.00, max 100.00)")
        sys.exit(1)
    try:
        amount = float(args[1])
    except ValueError:
        print(f"Invalid amount: {args[1]!r}")
        sys.exit(1)
    c = _client()
    _hr(f"BUY CREDITS — {amount:.2f} EUR")
    result = c.buy_credits(amount)
    print(f"  Added:   {result.get('credits_added', 'N/A')} EUR")
    print(f"  Balance: {result.get('balance', 'N/A')} EUR")
    print(f"  Proofs:  {result.get('proofs_available', 'N/A')} available")
    if result.get("receipt_url"):
        print(f"  Receipt: {result['receipt_url']}")
    _hr("DONE")


def _cmd_scan(args: list):
    positional = [a for a in args[1:] if not a.startswith("--")]
    if not positional:
        print("Usage: arkforge scan <repo_url>")
        sys.exit(1)
    repo_url = positional[0]
    if not repo_url.startswith(("http://", "https://")):
        print(f"Invalid URL: {repo_url!r}")
        sys.exit(1)
    receipt_url = _extract_receipt_url(args)
    c = _client()
    _hr("EU AI ACT COMPLIANCE SCAN")
    print(f"Repo:      {repo_url}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    result = c.scan_repo(repo_url, receipt_url=receipt_url)
    svc = result.get("service_response", {})
    upstream = svc.get("body", svc) if isinstance(svc, dict) else {}
    scan = upstream.get("scan_result", upstream) if isinstance(upstream, dict) else {}
    report = scan.get("report", scan) if isinstance(scan, dict) else {}
    compliance = report.get("compliance_summary", {}) if isinstance(report, dict) else {}
    if compliance:
        print("[SCAN RESULT]")
        print(f"  Compliance: {compliance.get('compliance_score', 'N/A')} "
              f"({compliance.get('compliance_percentage', 'N/A')}%)")
        print(f"  Risk cat:   {compliance.get('risk_category', 'N/A')}")
        print()
    _print_payment(result)
    _print_proof(result)
    _hr("DONE")


def _cmd_verify(args: list):
    if len(args) < 2:
        print("Usage: arkforge verify <proof_id>")
        sys.exit(1)
    c = _client()
    result = c.verify_proof(args[1])
    print(json.dumps(result, indent=2))


def _cmd_reputation(args: list):
    if len(args) < 2:
        print("Usage: arkforge reputation <agent_id>")
        sys.exit(1)
    c = _client()
    result = c.get_reputation(args[1])
    _hr(f"REPUTATION — {args[1]}")
    print(f"  Score:        {result.get('reputation_score', 'N/A')}/100")
    scoring = result.get("scoring", {})
    if scoring:
        print(f"  Success rate: {scoring.get('success_rate', 'N/A')}%")
        print(f"  Confidence:   {scoring.get('confidence', 'N/A')}")
    print(f"  Total proofs: {result.get('total_proofs', 'N/A')}")
    _hr()


def _cmd_dispute(args: list):
    positional = [a for a in args[1:] if not a.startswith("--")]
    if len(positional) < 2:
        print('Usage: arkforge dispute <proof_id> "reason"')
        sys.exit(1)
    c = _client()
    result = c.file_dispute(positional[0], positional[1])
    _hr("DISPUTE FILED")
    print(f"  Dispute ID: {result.get('dispute_id', 'N/A')}")
    print(f"  Status:     {result.get('status', 'N/A')}")
    print(f"  Resolution: {result.get('resolution', 'PENDING')}")
    _hr()


def _cmd_disputes(args: list):
    if len(args) < 2:
        print("Usage: arkforge disputes <agent_id>")
        sys.exit(1)
    c = _client()
    result = c.get_disputes(args[1])
    _hr(f"DISPUTES — {args[1]}")
    summary = result.get("summary", {})
    print(f"  Filed: {summary.get('total_filed', result.get('total', 0))}")
    print(f"  Won:   {summary.get('won', 0)}  Lost: {summary.get('lost', 0)}")
    for d in result.get("disputes", [])[:10]:
        print(f"  {d.get('dispute_id', 'N/A')} | {d.get('proof_id', 'N/A')} | {d.get('status', 'N/A')}")
    _hr()


def _fetch_tools_from_url(server_url: str) -> list:
    for url in [f"{server_url}/manifest.json", f"{server_url}/tools", f"{server_url}/v1/tools"]:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                raw = resp.json()
                tools = raw.get("tools", raw) if isinstance(raw, dict) else raw
                if isinstance(tools, list) and tools:
                    print(f"[SERVER] {len(tools)} tools from {url}")
                    return tools
        except Exception:
            continue
    try:
        resp = requests.post(
            server_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            tools = resp.json().get("result", {}).get("tools", [])
            if isinstance(tools, list) and tools:
                return tools
    except Exception:
        pass
    print(f"[ERROR] Could not fetch tools from {server_url}")
    sys.exit(1)


def _cmd_assess(args: list):
    positional = [a for a in args[1:] if not a.startswith("--")]
    use_demo = "--demo" in args
    url_idx = next((i for i, a in enumerate(args) if a == "--url"), None)

    if use_demo:
        server_id = "demo-mcp-server"
        tools = _DEMO_TOOLS
    elif url_idx is not None and url_idx + 1 < len(args):
        server_url = args[url_idx + 1]
        server_id = positional[0] if positional else server_url.rstrip("/").split("/")[-1]
        tools = _fetch_tools_from_url(server_url)
    elif positional:
        server_id = positional[0]
        # Read tools from stdin if piped
        if not sys.stdin.isatty():
            try:
                tools = json.load(sys.stdin)
                if isinstance(tools, dict):
                    tools = tools.get("tools", [])
            except Exception:
                print("[ERROR] Could not parse tools JSON from stdin")
                sys.exit(1)
        else:
            print("Usage: arkforge assess <server_id> [--url <server_url> | --demo]")
            print("       echo '[...]' | arkforge assess <server_id>")
            sys.exit(1)
    else:
        print("Usage: arkforge assess <server_id> [--url <server_url> | --demo]")
        sys.exit(1)

    server_version = next(
        (args[i + 1] for i, a in enumerate(args) if a == "--version" and i + 1 < len(args)), ""
    )
    c = _client()
    result = c.assess_mcp(server_id, tools, server_version)

    risk = result.get("risk_score", 0)
    risk_label = "HIGH" if risk >= 70 else "MEDIUM" if risk >= 40 else "LOW" if risk >= 10 else "CLEAN"
    _hr(f"MCP ASSESSMENT — {result.get('server_id', server_id)}")
    print(f"  Risk score:  {risk}/100  [{risk_label}]")
    print(f"  Baseline:    {result.get('baseline_status', 'N/A')}")
    drift = result.get("drift_detected", False)
    print(f"  Drift:       {'YES' if drift else 'no'}")
    if drift and result.get("drift_summary"):
        print(f"  Summary:     {result['drift_summary']}")
    print()
    findings = result.get("findings", [])
    if findings:
        print(f"  Findings ({len(findings)}):")
        for f in sorted(findings, key=lambda x: ["critical","high","medium","low","info"].index(x.get("severity","info")) if x.get("severity","info") in ["critical","high","medium","low","info"] else 99):
            sev = f.get("severity", "info").upper()
            tool = f.get("tool", "")
            msg = f.get("message", "")
            print(f"    [{sev}] {tool + ': ' if tool else ''}{msg}")
    else:
        print("  Findings: none")
    _hr()


def _cmd_compliance(args: list):
    from datetime import date, timedelta
    today = date.today()
    date_from = (today - timedelta(days=90)).isoformat()
    date_to = today.isoformat()
    framework = next(
        (args[i + 1] for i, a in enumerate(args) if a == "--framework" and i + 1 < len(args)),
        "eu_ai_act",
    )
    c = _client()
    result = c.compliance_report(date_from, date_to, framework)
    dr = result.get("date_range", {})
    _hr(f"COMPLIANCE REPORT — {result.get('framework', framework).upper()}")
    print(f"  Report ID:  {result.get('report_id', 'N/A')}")
    print(f"  Period:     {dr.get('from','?')[:10]} → {dr.get('to','?')[:10]}")
    print(f"  Proofs:     {result.get('proof_count', 0)}")
    summary = result.get("summary", {})
    print(f"  Covered:    {summary.get('covered', 0)}")
    print(f"  Partial:    {summary.get('partial', 0)}")
    print(f"  Gaps:       {summary.get('gap', 0)}")
    gaps = result.get("gaps", [])
    if gaps:
        print()
        print("  Gaps to address:")
        for g in gaps:
            print(f"    - {g}")
    _hr()


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        sys.exit(0)
    if args[0] in ("-v", "--version", "version"):
        print(f"arkforge {__version__}")
        sys.exit(0)

    cmd = args[0]
    try:
        if cmd == "pay":
            _cmd_pay(args)
        elif cmd == "credits":
            _cmd_credits(args)
        elif cmd == "scan":
            _cmd_scan(args)
        elif cmd == "verify":
            _cmd_verify(args)
        elif cmd == "reputation":
            _cmd_reputation(args)
        elif cmd == "dispute":
            _cmd_dispute(args)
        elif cmd == "disputes":
            _cmd_disputes(args)
        elif cmd == "assess":
            _cmd_assess(args)
        elif cmd == "compliance":
            _cmd_compliance(args)
        else:
            print(f"Unknown command: {cmd!r}\n")
            print(USAGE)
            sys.exit(1)
    except AuthError as e:
        print(f"[AUTH ERROR] {e}")
        print("Set TRUST_LAYER_API_KEY or pass api_key= to TrustLayerClient()")
        sys.exit(1)
    except APIError as e:
        print(f"[API ERROR] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
