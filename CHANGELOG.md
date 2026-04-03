# Changelog

## [1.9.3] - 2026-04-03

### Changed
- `README.md` — compliance section updated for all 4 frameworks (eu_ai_act, iso_42001,
  nist_ai_rmf, soc2_readiness): framework table, CLI examples for each, NIST AI RMF
  example output, SOC 2 audit disclaimer, commands table, library usage examples.

---

## [1.9.2] - 2026-04-03

### Added
- `compliance --framework iso_42001` — ISO/IEC 42001:2023 AI Management System report,
  in addition to the existing `eu_ai_act` default.
- 7 new tests for `compliance_report()` — both frameworks, default value, framework
  passed through to server, no API key, unknown framework, server error.

### Changed
- `compliance_report()` docstring updated: lists `eu_ai_act` and `iso_42001` as supported frameworks.
- CLI usage text: `compliance` command now shows both framework options.
- `_print_compliance_report()`: "articles" → "clauses/articles" (framework-agnostic).

---

## [1.9.1] - 2026-04-03

### Added
- `assess --server-url https://mcp.example.com` — fetch tools list from a remote MCP server
  before calling `/v1/assess`. Tries in order: `GET /manifest.json`, `GET /tools`,
  `GET /v1/tools`, MCP JSON-RPC `tools/list`. Useful when the client runs on a different
  machine than the server.

## [1.9.0] - 2026-04-03

### Added
- `assess <server_id>` command — MCP server security posture assessment.
  Analyzes a manifest for dangerous capability patterns (`PermissionAnalyzer`:
  filesystem write, code execution, env access, network), tool drift since the
  last baseline (`DescriptionDriftAnalyzer`), and version regressions
  (`VersionTrackingAnalyzer`). Returns a `risk_score` (0–100) with categorized
  findings. `--demo` flag uses a built-in manifest for quick testing.
  `--tools-file manifest.json` reads tools from a JSON file.
  `--version 1.0.0` tracks server version changes. Rate limit: 100/day, no credits.
- `compliance` command — EU AI Act compliance report.
  Aggregates all proofs for the current API key over a date range and maps
  them to 6 EU AI Act articles (Art. 9, 10, 13, 14, 17, 22).
  Returns per-article coverage status and a gaps list.
  `--from` / `--to` flags control the date range (defaults: last 30 days).
  `--framework` selects the framework (default: `eu_ai_act`). No credits consumed.
- `assess_mcp(server_id, tools, server_version)` library function.
- `compliance_report(date_from, date_to, framework)` library function.
- `_print_assessment()` and `_print_compliance_report()` display helpers.
- `_DEMO_TOOLS` built-in manifest (4 tools including dangerous patterns).

### Changed
- `AGENT_VERSION` bumped to `1.9.0`.
- `_save_log()` now saves `assess` and `compliance` prefixed log files.
- Module docstring updated to list all 9 commands.
- Architecture section in README updated (7 → 9 commands).

## [1.8.1] - 2026-03-16

### Changed (no code change — Trust Layer v1.3.0 API update)
- `verify_proof(proof_id)` — `GET /v1/proof/{id}` now returns a privacy-filtered response. The following fields are no longer visible publicly: `parties` (buyer/seller identity), `certification_fee` amounts, `provider_payment.receipt_url`, `provider_payment.parsed_fields` (amount, status, date), `buyer_reputation_score`, `buyer_profile_url`. `_print_provider_payment()` and `_print_payment()` will silently skip these fields when called on a verified proof.
- To access the full proof (including payment details), use `GET /v1/proof/{id}/full` with your API key (owner only). No client helper added yet — use `requests.get()` directly with `headers={"X-Api-Key": YOUR_KEY}`.

## [1.8.0] - 2026-03-03

### Added
- Display Sigstore Rekor entry in `_print_proof()` output
  - `Rekor: verified (logIndex=<N>)` when transparency log is present
  - `Rekor URL: https://search.sigstore.dev/?logIndex=<N>` for direct public verification

## [1.7.0] - 2026-03-03

### Changed
- `reputation` command updated to match new Trust Layer scoring model
  - Displays `reputation_score`, `success_rate`, `confidence`, and `formula`
  - Previous 5-dimension display (reliability, volume, etc.) removed — replaced by transparent formula
  - Formula: `score = floor(success_rate × confidence) − penalties`

## [1.6.0] - 2026-03-01

### Added
- `reputation <agent_id>` command — check public reputation score (0-100) for any agent
- `dispute <proof_id> "reason"` command — flag a proof as contested
- `disputes <agent_id>` command — view dispute history for an agent

### Changed
- Auto-save receipt after `credits` command (receipt URL logged for Mode B reference)
- Auto-attach receipt on `scan`/`pay` if `--receipt-url` provided

## [1.5.0] - 2026-02-28

### Added
- Mode B — payment evidence: `--receipt-url URL` attaches a direct provider payment receipt
- `--pay-provider` flag: pays the scan provider directly via Stripe and auto-attaches the receipt
- Ghost Stamp (Level 2): `X-ArkForge-*` response headers captured and displayed
- `--no-receipt` flag to skip receipt attachment

## [1.4.0] - 2026-02-26

### Added
- `credits <amount>` command — buy prepaid credits via Stripe Checkout (1–100 EUR)
- `verify <proof_id>` command — verify an existing proof
- Proof files saved to `proofs/` directory alongside transaction logs

### Changed
- `scan` and `pay` now debit prepaid credits (0.10 EUR/proof) instead of per-call Stripe charges
- Free tier support (100 proofs/month, no card required)

## [1.0.0] - 2026-02-17

### Added
- Initial release: `scan <repo_url>` and `pay` commands
- Trust Layer proxy integration (SHA-256 chain + Ed25519 + RFC 3161 TSA)
- Transaction logging to `logs/` directory
