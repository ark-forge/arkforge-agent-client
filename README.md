# ArkForge Agent Client

[![GitHub Stars](https://img.shields.io/github/stars/ark-forge/arkforge-agent-client?style=flat&label=Star)](https://github.com/ark-forge/arkforge-agent-client/stargazers)

A proof-of-concept demonstrating **autonomous agent-to-agent paid transactions** through the [ArkForge Trust Layer](https://github.com/ark-forge/trust-layer).

One agent (this client) calls another agent (the [ArkForge MCP EU AI Act](https://github.com/ark-forge/mcp-eu-ai-act) scanner) to scan a code repository for EU AI Act compliance. Every transaction flows through the Trust Layer, which produces a tamper-proof cryptographic proof (SHA-256 chain + Ed25519 signature + RFC 3161 certified timestamp + Sigstore Rekor public log entry).

**Free tier:** fully autonomous — the agent signs up and runs with a single curl, no card required.
**Pro tier:** one-time human setup (Stripe Checkout to save a card), fully autonomous after that.

## Quick Start

### 1. Get an API key

**Free plan** — no card required:

```bash
curl -X POST https://trust.arkforge.tech/v1/keys/free-signup \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com"}'
```

Your `mcp_free_*` API key will be emailed automatically. 100 calls/month, 3 witnesses (Ed25519, RFC 3161, Sigstore Rekor — no Stripe required).

**Pro plan** — buy initial credits and save card (once):

**Option A — via setup_card.py:**

```bash
python3 setup_card.py your@email.com --test    # Test mode (Stripe test card)
python3 setup_card.py your@email.com           # Live mode (real charges)
```

**Option B — via curl:**

```bash
curl -X POST https://trust.arkforge.tech/v1/keys/setup \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "mode": "test", "amount": 10}'
```

Open the returned `checkout_url` in a browser. The initial purchase (minimum 10 EUR = 100 proofs) is charged immediately and your card is saved for future top-ups. For test mode, use Stripe test card `4242 4242 4242 4242` (any future expiry, any CVC). Your API key and credits are set up automatically after payment.

### 2. Top up credits (Pro plan)

Buy more credits any time — the saved card is charged directly, no browser required.

**Via agent.py:**

```bash
pip install requests
export TRUST_LAYER_API_KEY="mcp_pro_..."
python3 agent.py credits 10    # Buy 10 EUR = 100 proofs — receipt auto-saved
```

**Via curl:**

```bash
curl -X POST https://trust.arkforge.tech/v1/credits/buy \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: mcp_pro_..." \
  -d '{"amount": 10}'
# Returns: {"credits_added": 10.0, "balance": 10.0, "proofs_available": 100, ...}
```

Each proof costs 0.10 EUR. Min 1 EUR, max 100 EUR. Credits are deducted automatically on each proxy call. Credits never expire.

### 3. Run a scan

```bash
export TRUST_LAYER_API_KEY="mcp_test_..."    # or mcp_pro_... for live
python3 agent.py scan https://github.com/owner/repo
```

If you purchased credits earlier, the saved receipt is **auto-attached** as payment evidence. You can also provide one manually:

```bash
python3 agent.py scan https://github.com/owner/repo \
  --receipt-url "https://pay.stripe.com/receipts/payment/CAcaFwoV..."
```

To skip auto-attach for a single call:

```bash
python3 agent.py scan https://github.com/owner/repo --no-receipt
```

**Mode B PoC — pay the scan provider directly via Stripe:**

```bash
export STRIPE_SECRET_KEY="sk_test_..."       # your agent's Stripe key
export STRIPE_PAYMENT_METHOD="pm_xxx"        # saved payment method
export SCAN_PROVIDER_PRICE="100"             # optional, cents EUR (default: 100 = 1.00 EUR)
python3 agent.py scan https://github.com/owner/repo --pay-provider
```

The agent creates a Stripe `PaymentIntent` off-session, retrieves the `receipt_url` from the resulting `Charge`, and attaches it automatically as `provider_payment` to the Trust Layer call. ArkForge does not handle this money — the payment goes directly between agents.

### 4. Just pay (no scan)

```bash
python3 agent.py pay                     # auto-attaches saved receipt if any
python3 agent.py pay --no-receipt        # skip auto-attach
python3 agent.py pay --receipt-url "https://pay.stripe.com/receipts/payment/..."
```

### 5. Verify a proof

```bash
python3 agent.py verify prf_20260225_171714_4ebb28
```

### 6. Check reputation

```bash
python3 agent.py reputation <agent_id>
```

```
============================================================
AGENT REPUTATION
============================================================
  Agent:       sha256:buyer_abc123...
  Score:       85/100
  Success rate:  100.0%
  Confidence:    0.85
  Formula:       floor(success_rate × confidence) − penalties
  Total proofs:  10
  Signature:   ed25519:T3hY8kLm9nPq...(verified)
============================================================
```

The score is publicly auditable: `score = floor(success_rate × confidence)`.
Confidence grows with volume (0.60 at 1 proof → 1.00 at 20+ proofs).
One optional penalty: −15 if the agent changed its declared identity.

### 7. File a dispute

```bash
python3 agent.py dispute prf_20260301_120000_abc123 "Response was empty"
```

```
============================================================
DISPUTE FILED
============================================================
  Dispute ID:  disp_a1b2c3d4
  Proof ID:    prf_20260301_120000_abc123
  Status:      open
  Resolution:  PENDING
============================================================
```

### 8. View dispute history

```bash
python3 agent.py disputes <agent_id>
```

```
============================================================
DISPUTE HISTORY
============================================================
  Filed:       3
  Won:         2
  Lost:        1

  Recent disputes:
    disp_a1b2c3d4 | prf_20260301_120000_abc123 | UPHELD
    disp_e5f6g7h8 | prf_20260228_090000_def456 | DENIED
    disp_i9j0k1l2 | prf_20260227_150000_ghi789 | UPHELD
============================================================
```

### 9. Assess an MCP server

Analyze an MCP server manifest for security risks: dangerous capabilities, tool drift since the last call, version changes.

**Quick demo** (built-in manifest with intentionally dangerous tools):

```bash
python3 agent.py assess my-mcp-server --demo
```

**From a manifest file:**

```bash
# tools.json — list of tool objects (name + description minimum)
python3 agent.py assess my-mcp-server --tools-file tools.json --version 1.2.0
```

**From a remote MCP server** (client and server on different machines):

```bash
python3 agent.py assess my-mcp-server --server-url https://mcp.example.com --version 1.5.0
```

The client tries in order: `GET /manifest.json`, `GET /tools`, `GET /v1/tools`, then MCP JSON-RPC `tools/list`. First successful response with a non-empty tools list is used.

```json
[
  {"name": "get_weather", "description": "Fetch weather from public API"},
  {"name": "read_file",   "description": "Read any file from the local filesystem"},
  {"name": "exec_shell",  "description": "Execute a shell command"}
]
```

**Example output:**

```
============================================================
MCP SECURITY ASSESSMENT — my-mcp-server
============================================================
  Assessment ID:  asr_20260403_121500_a1b2c3
  Assessed at:    2026-04-03T12:15:00Z
  Risk score:     75/100  [HIGH]
  Baseline:       updated
  Drift detected: YES
  Drift summary:  1 tool added: exec_shell

  Findings (3 total):
    [CRITICAL] exec_shell: Tool description matches code execution pattern
    [HIGH] read_file: Tool description matches filesystem read pattern
    [MEDIUM] get_weather: network_access pattern detected
============================================================
```

Call the same server twice to see drift detection in action — the second call compares against the baseline saved by the first.

Rate limit: 100 assessments/day per API key. No credits consumed.

### 10. Generate a compliance report

Aggregate all proofs certified under your API key over a date range and map them to EU AI Act articles.

```bash
# Last 30 days (default)
python3 agent.py compliance

# Custom range
python3 agent.py compliance --from 2026-01-01 --to 2026-12-31
```

**Example output:**

```
============================================================
COMPLIANCE REPORT — EU_AI_ACT
============================================================
  Report ID:      rpt_20260403_122000_d4e5f6
  Framework:      eu_ai_act v1.0
  Date range:     2026-01-01 → 2026-04-03
  Proofs analyzed:47

  Summary (6 articles):
    Covered:        3
    Partial:        2
    Gap:            0
    Not applicable: 1

  Article coverage:
    [OK] Art. 9 — Risk Management Systems: covered
    [NA] Art. 10 — Data and Data Governance: not applicable
    [OK] Art. 13 — Transparency and Provision of Information: covered
    [~~] Art. 14 — Human Oversight: partial
         agent_identity_verified not set on all proofs
    [OK] Art. 17 — Quality Management System: covered
    [~~] Art. 22 — Record-Keeping: partial
         47 proofs found; extend date range for full coverage

  No gaps identified.
============================================================
```

Requires proofs created after Trust Layer v1.3.18 (or a backfill run). No credits consumed.

### Example scan output

```
============================================================
EU AI ACT COMPLIANCE SCAN — via Trust Layer
============================================================
Timestamp:   2026-02-25T17:17:12.560154+00:00
Target:      https://github.com/openai/openai-quickstart-python
Price:       0.10 EUR (from prepaid credits)
Trust Layer: https://trust.arkforge.tech/v1/proxy
Scan API:    https://arkforge.tech/api/v1/scan-repo
API Key:     mcp_te...

[PAYMENT]
  Amount:    0.1 eur
  Status:    succeeded
  Txn ID:    crd_20260227_143012_a1b2c3

[SCAN RESULT]
  Compliance:  2/3 (66.7%)
  Risk Cat:    limited
  Frameworks:  openai, anthropic

[PROOF — Trust Layer]
  ID:           prf_20260225_171714_4ebb28
  Spec:         1.1
  Chain Hash:   sha256:5319f160352fea2c1889cf6dcbb9d1b431...
  Request Hash: sha256:0b801bccb76376504cb2c5f92c55cd7cfd...
  Signature:    ed25519:T3hY8k...(verified)
  Verify URL:   https://trust.arkforge.tech/v1/proof/prf_20260225_171714_4ebb28
  Share URL:    https://arkforge.tech/trust/v/prf_20260225_171714_4ebb28
  Timestamp:    2026-02-25T17:17:12Z
  Upstream:     Wed, 25 Feb 2026 17:17:13 GMT
  TSA:          pending

[ATTESTATION — Digital Stamp]
  Embedded in scan result body as _arkforge_attestation
  Status:       VERIFIED_TRANSACTION

[RESPONSE HEADERS — Ghost Stamp]
  X-ArkForge-Verified: true
  X-ArkForge-Proof-ID: prf_20260225_171714_4ebb28
  X-ArkForge-Trust-Link: https://arkforge.tech/trust/v/prf_20260225_171714_4ebb28

[SAVED] logs/scan_20260225_171715.json
============================================================
```

With `--receipt-url` or `--pay-provider`, an additional section appears:

```
[PAYMENT EVIDENCE — External Receipt]
  Fetch:     OK (fetched)
  Hash:      sha256:af65b75f3901dfd0ed9590a009bf7283e318...
  Parsing:   success
  Amount:    25.0 usd
  Status:    Paid
  Date:      February 28, 2026
  Verified:  fetched
```

With `--pay-provider`, the Stripe payment is shown before the scan:

```
[MODE B] Paying scan provider directly via Stripe (1.00 EUR)...
[MODE B] PaymentIntent: pi_3Pxxx
[MODE B] Amount:        1.00 EUR
[MODE B] Receipt:       https://pay.stripe.com/receipts/payment/CAcaFwoV...

============================================================
EU AI ACT COMPLIANCE SCAN — via Trust Layer
============================================================
...
Receipt URL: https://pay.stripe.com/receipts/payment/CAcaFwoV...
```

The proof is emitted with `spec_version: 2.0` and includes `receipt_content_hash` in the chain.

## Library usage

`agent.py` can be imported as a Python module:

```python
from agent import (
    scan_repo, verify_proof, get_reputation, file_dispute, get_disputes,
    assess_mcp, compliance_report,
)

# All functions return dicts — check for "error" key on failure
result = scan_repo("https://github.com/owner/repo")
if "error" in result:
    print(result["error"])
else:
    proof = result["proof"]
    print(proof["proof_id"])

# Public endpoints (no API key required)
rep = get_reputation("buyer_abc123")
disputes = get_disputes("buyer_abc123")

# Authenticated endpoints (TRUST_LAYER_API_KEY env var)
result = file_dispute("prf_...", "Response was empty")
```

Config is read from environment variables at call time, so you can set them after import:

```python
import os
os.environ["TRUST_LAYER_API_KEY"] = "mcp_pro_..."
os.environ["TRUST_LAYER_BASE"] = "http://localhost:8100"  # local dev

from agent import scan_repo
result = scan_repo("https://github.com/owner/repo")
```

## Why does this matter?

AI agents are starting to act on behalf of humans — browsing, coding, deploying. The next step is agents **paying for services autonomously**. But autonomous payments create a trust problem:

- How does the buyer agent know it got what it paid for?
- How does the seller agent prove it delivered?
- How does the human owner verify what happened?

## How the Trust Layer works

Every transaction produces a chain of verifiable proofs:

```
Agent Client
    |
    v
Trust Layer (/v1/proxy)
    |--- Validates API key
    |--- Debits prepaid credits (Pro only — Free skips this)
    |--- Fetches external receipt if --receipt-url provided (optional)
    |--- Forwards scan request to upstream API
    |--- Hashes request + response (SHA-256 chain)
    |--- Binds receipt content hash to chain (if present)
    |--- Signs with Ed25519
    |--- Submits to RFC 3161 TSA (certified timestamp)
    |--- Returns proof + scan result
    |
    v
Agent receives: scan report + cryptographic proof [+ payment evidence]
```

**Each layer is independently verifiable:**

| Proof | Verified by | Can be faked? | Plan |
|---|---|---|---|
| Ed25519 signature | Verify with ArkForge public key | No (cryptographic) | All |
| SHA-256 hash chain | Trust Layer verification URL | No (deterministic) | All |
| RFC 3161 TSA | `openssl ts -verify` | No (certified by trusted TSA) | All |
| Sigstore Rekor | [search.sigstore.dev](https://search.sigstore.dev) — public log by Linux Foundation | No (append-only public log) | All |
| Stripe receipt | Stripe dashboard (for credit purchase) | No (Stripe is source of truth) | Pro only |
| External receipt | `--receipt-url` — fetched, hashed, bound to proof | No (SHA-256 of raw content) | All (optional) |
| Scan result | Re-running scan on same repo | No (deterministic) | All |
| Local log | `logs/*.json` + `proofs/*.json` | Tamper-evident (contains hashes) | All |

### Three-layer proof system

Every transaction carries the ArkForge mark at 3 levels:

| Level | Where | For whom | What |
|-------|-------|----------|------|
| **1 — Digital Stamp** | `service_response.body._arkforge_attestation` | Agents (JSON consumers) | Proof ID, seal URL, verification status |
| **2 — Ghost Stamp** | HTTP response headers | Infra / monitoring | `X-ArkForge-Verified`, `X-ArkForge-Proof-ID`, `X-ArkForge-Trust-Link` |
| **3 — Visual Stamp** | HTML proof page | Humans / legal | Colored badge (green/orange/red), full proof details |

Open any proof in a browser: `https://arkforge.tech/trust/v/prf_...` — the short URL redirects to a self-contained HTML page with all verification details.

## Transparency Notice

Both this agent (buyer) and the ArkForge scan API (seller) are built and controlled by the same team (ArkForge). This is a proof-of-concept — not an attempt to simulate independent entities. The architecture is designed so that it **would work identically** between independent parties.

## Proof fields

| Field | Description |
|-------|-------------|
| `proof.spec_version` | Proof format version: `1.1` (standard) or `2.0` (with receipt). See [proof-spec](https://github.com/ark-forge/proof-spec) |
| `proof.arkforge_signature` | Ed25519 signature of the chain hash |
| `proof.arkforge_pubkey` | ArkForge's public key for verification |
| `proof.upstream_timestamp` | Upstream service's `Date` header |
| `proof.timestamp_authority.tsr_base64` | Embedded TSR file (base64, available after background processing) |
| `proof.provider_payment` | Provider payment receipt verification — present when `--receipt-url` or `--pay-provider` was used (Mode B). Not the ArkForge certification fee. |
| `proof.provider_payment.receipt_content_hash` | SHA-256 of raw receipt bytes — bound to chain hash (triggers spec 2.0) |
| `proof.provider_payment.parsed_fields` | Extracted amount, currency, status, date (best-effort) |
| `proof.transaction_success` | Whether the upstream service returned a success response (HTTP status < 400) |
| `proof.upstream_status_code` | HTTP status code returned by the upstream service |
| `proof.disputed` | Whether this proof has been disputed |
| `proof.dispute_id` | Reference to the dispute record (e.g. `disp_a1b2c3d4`) |

## Commands

| Command | Description |
|---------|-------------|
| `python3 agent.py scan <repo_url>` | Scan repo via Trust Layer (auto-attaches saved receipt) |
| `python3 agent.py scan <repo_url> --pay-provider` | Mode B PoC: pay provider via Stripe then scan (proof spec 2.0) |
| `python3 agent.py scan <repo_url> --receipt-url URL` | Attach a manual provider receipt (Mode B, manual) |
| `python3 agent.py scan <repo_url> --no-receipt` | Skip auto-attach for this call |
| `python3 agent.py pay [--receipt-url URL] [--no-receipt]` | Payment + proof only (auto-attaches saved receipt) |
| `python3 agent.py credits <amount>` | Buy prepaid credits — **saves receipt URL** for future calls |
| `python3 agent.py verify <proof_id>` | Verify an existing proof (shows payment evidence if present) |
| `python3 agent.py reputation <agent_id>` | Check agent reputation score (0-100) |
| `python3 agent.py dispute <proof_id> "reason"` | File a dispute against a proof |
| `python3 agent.py disputes <agent_id>` | View dispute history for an agent |
| `python3 agent.py assess <server_id> --demo` | Assess MCP server security posture (built-in demo manifest) |
| `python3 agent.py assess <server_id> --tools-file f.json` | Assess MCP server from manifest file |
| `python3 agent.py assess <server_id> --server-url URL [--version V]` | Fetch manifest from remote server, then assess |
| `python3 agent.py compliance` | EU AI Act compliance report (last 30 days) |
| `python3 agent.py compliance --from DATE --to DATE` | Compliance report for a custom date range |

## Plans

| Key prefix | Plan | Stripe | Witnesses | Limits |
|---|---|---|---|---|
| `mcp_free_*` | Free | No | 3 (Ed25519, RFC 3161 TSA, Sigstore Rekor) + optional external receipt | 100/month |
| `mcp_test_*` | Test | Test mode (no real charges) | 3 + optional external receipt | Dev only |
| `mcp_pro_*` | Pro | Prepaid credits (0.10 EUR/proof) | 3 (+ Stripe receipt) + optional external receipt | 100/day |

## Prerequisites

- Python 3.10+
- `pip install requests`
- `pip install stripe` (only for `--pay-provider`)

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUST_LAYER_API_KEY` | — | API key (required) |
| `TRUST_LAYER_BASE` | `https://trust.arkforge.tech` | Trust Layer URL |
| `SCAN_API_TARGET` | `https://arkforge.tech/api/v1/scan-repo` | Upstream scan endpoint |
| `STRIPE_SECRET_KEY` | — | Agent's Stripe secret key (`sk_test_…` / `sk_live_…`) — Mode B only |
| `STRIPE_PAYMENT_METHOD` | — | Saved Stripe payment method ID (`pm_…`) — Mode B only |
| `SCAN_PROVIDER_PRICE` | `100` | Provider payment amount in cents EUR (100 = 1.00 EUR) — Mode B only |

## Architecture

```
arkforge-agent-client/
  agent.py               # CLI + importable library (9 commands)
  setup_card.py          # One-time: buy initial credits + save card via Stripe Checkout
  requirements.txt       # requests + stripe (optional for --pay-provider)
  .last_receipt.json     # Auto-saved Stripe receipt URL (gitignored)
  logs/                  # Transaction logs (JSON, gitignored)
  proofs/                # Cryptographic proofs (JSON, gitignored)
```

## Roadmap

Third-party provider support and multi-PSP payment verification are coming. See the [Trust Layer roadmap](https://github.com/ark-forge/trust-layer/blob/main/ROADMAP.md).

## License

MIT

---

Questions or feedback? Open an [issue](https://github.com/ark-forge/arkforge-agent-client/issues).
