# jhcontext-sdk — Session Continuation Instructions

## What was done

### Paper (jhcontext-paper8pgs/)
- 8-page version of PAC-AI paper for IADIS AIS 2026 (Valencia, deadline Apr 10)
- Renamed PAC-P → **PAC-AI** (Protocol for Auditable Context in AI)
- Scenarios: Healthcare (Art. 14, temporal oversight) + Education (Art. 13, negative proof)
- IADIS formatting, APA bibliography, blind review ready
- Currently 9 pages (needs ~2 lines trimmed to fit 8)
- Figure 1 (pacp-layers.jpeg) still says "PAC-P" — needs regenerated image

### SDK (jhcontext-sdk/) — v0.2.0, IMPLEMENTED
Core modules all working and tested:
- `jhcontext/models.py` — Pydantic models (Envelope, Artifact, DecisionInfluence, Privacy, Compliance, Proof, Decision)
- `jhcontext/builder.py` — EnvelopeBuilder fluent API
- `jhcontext/prov.py` — PROVGraph (rdflib W3C PROV builder with query helpers)
- `jhcontext/audit.py` — verify_temporal_oversight, verify_negative_proof, verify_workflow_isolation, verify_integrity
- `jhcontext/crypto.py` — SHA-256, Ed25519 sign/verify (HMAC fallback without cryptography pkg)
- `jhcontext/canonicalize.py` — JSON deterministic serialization
- `jhcontext/semantics.py` — UserML helpers (observation, interpretation, situation)
- `jhcontext/server/app.py` — FastAPI app factory
- `jhcontext/server/routes/` — envelopes, artifacts, decisions, provenance, compliance routes
- `jhcontext/server/storage/sqlite.py` — SQLite backend (zero-config, ~/.jhcontext/)
- `jhcontext/server/mcp_server.py` — MCP server with tools (submit_envelope, get_envelope, query_prov, run_audit)
- `jhcontext/client/api_client.py` — REST client (httpx)
- `jhcontext/cli.py` — CLI: `jhcontext serve`, `jhcontext mcp`, `jhcontext version`
- `pyproject.toml` — hatchling, extras: [server], [crewai], [all], [dev]

### Protocol spec (jhcontext-protocol/)
- `jhcontext-core.jsonld` — Updated to v0.3 with artifacts_registry, decision_influence, privacy, compliance, scope, passed_artifact_pointer

### Agent definitions (jhcontext-agent/)
- `paper-agent.yaml` — Paper revision agent + task
- `author_actions.md` — Detailed plan with CrewAI agents for both scenarios

## What remains to be done

### Priority 1: Tests + README
- Write formal pytest tests for all modules (test_models, test_builder, test_prov, test_audit, test_crypto, test_storage, test_api)
- Write README.md with architecture overview, install modes, usage examples
- Run full test suite: `pip install -e ".[all,dev]" && pytest`

### Priority 2: jhcontext-usecases repo
- Create `/home/jhdarosa/Repos/jhcontext-usecases/`
- Healthcare scenario: 5 CrewAI agents (sensor→situation→decision→oversight→audit) using jhcontext SDK
- Education scenario: 4 CrewAI agents (ingestion→grading→equity→audit) with workflow isolation
- Agent YAML definitions are in `jhcontext-agent/author_actions.md` — use as reference
- Each scenario should produce: envelope JSON, PROV Turtle, audit report JSON
- Entry points: `python -m usecases.healthcare.run`, `python -m usecases.education.run`

### Priority 3: Server testing
- Test FastAPI server: `jhcontext serve` → hit endpoints with httpx
- Test MCP server: `jhcontext mcp` → verify tools work via stdio
- Test client↔server flow end-to-end

### Priority 4: Paper updates
- Trim paper to 8 pages (currently 9 — needs ~2 lines cut)
- Update Figure 1 image (still says PAC-P instead of PAC-AI)
- After usecases run: add implementation evidence to paper (envelope snippets, PROV graphs, metrics)

### Priority 5: Publish
- Publish jhcontext to PyPI: `python -m build && twine upload dist/*`
- Push to GitHub (public repo)
- For blind review: use anonymous.4open.science for paper reference

## Key files to read for context
1. `/home/jhdarosa/.claude/plans/cached-toasting-turing.md` — Full implementation plan
2. `/home/jhdarosa/Repos/jhcontext-agent/author_actions.md` — CrewAI agent definitions + scenario specs
3. `/home/jhdarosa/Repos/jhcontext-paper8pgs/sections/05scenarios.tex` — Paper scenario descriptions
4. `/home/jhdarosa/Repos/jhcontext-sdk/pyproject.toml` — Package structure and dependencies

## Quick verification commands
```bash
# Test SDK works
cd /home/jhdarosa/Repos/jhcontext-sdk
pip install -e ".[dev]"
python -c "from jhcontext import EnvelopeBuilder, PROVGraph; print('OK')"

# Start server
pip install -e ".[server]"
jhcontext serve  # FastAPI on localhost:8400

# Start MCP
jhcontext mcp  # stdio transport
```
