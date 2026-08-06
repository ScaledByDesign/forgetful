# Forgetful Development Guide

## Architecture
Layered architecture:
 routes -> services -> protocols -> repositories/adapters 
No pollution of service layer with integration/implementation details

## Testing Philosophy
We focus on **integration and E2E tests** over unit tests. Tests should cover critical workflows without exhaustive edge case coverage.

### Integration Tests
**Location**: `tests/integration/`
**Purpose**: Test business logic with stubbed I/O (no real database required)
**Run locally**:
```bash
uv run pytest tests/integration/
```
These tests use in-memory stubs and run fast (~seconds). They form the bulk of our test suite and catch 90% of issues.

### End-to-End Tests

#### SQLite E2E Tests
**Location**: `tests/e2e_sqlite/`
**Purpose**: Test complete stack with in-memory SQLite
**Requirements**: None (no Docker required)
**Run locally**:
```bash
uv run pytest tests/e2e_sqlite/
```
These tests use an in-memory SQLite database for test isolation. Fast execution with automatic cleanup. 

#### PostgreSQL E2E Tests
**Location**: `tests/e2e/`
**Purpose**: Test complete stack with real PostgreSQL
**Requirements**: PostgreSQL running in Docker
**Run locally**:
```bash
cd docker && docker compose down -v  
uv run pytest -m e2e
```
**Remember**: rebuild docker image if running local container service, not required however for e2e tests.


## Linting
Ensure that you run ruff following any changes and address any issues raised
```bash
uv tool run ruff check .
```

**Note**: Ruff UP006 rule enforces Python 3.12+ built-in generics (`list` instead of `typing.List`, `dict` instead of `typing.Dict`, etc.). This catches legacy type hint syntax automatically.

<!-- BEGIN DELEGATE-PLANES v2026-08-02 (managed block — edit inside markers only; rollout: memory plane #31374) -->
# Delegate System Architecture — the three planes

Every agent (Claude Code session, subagent, cluster pod) uses the same three service planes. Route by concern:

| Plane | Endpoint | Use for |
|---|---|---|
| **Memory** | `memory.delegate.ws` (Forgetful MCP) | THE global memory & knowledge base: decisions, gotchas, architecture facts, completion records. System of record — local `memory/` dirs, `docs/memory/`, and wikis are per-project caches/indexes. |
| **Connect** | `connect.delegate.ws` (Delegate Connect MCP) | ALL agentic access to external systems: 1,000+ SaaS providers, MCP/API tools, governed credentials. Never hold raw credentials the gateway can hold for you. |
| **Cluster** | `cluster.delegate.ws` (Cluster MCP → Argo pods) | Agentic clusters & sub-agent fleets for long-running/parallel/remote work beyond the local session. Pods carry `memory_recall`/`memory_store` and reach the same planes. |

**Operating pattern — recall → execute → validate → review → finalize:**
1. **Recall is step 0.** `query_memory` on the memory plane (multiple phrasings — one miss is not "not in memory") BEFORE researching, planning, or asking the user. Recall again mid-work on any unfamiliar system or suspected-known error.
2. **Execute** the smallest change that satisfies recalled knowledge (DRY/KISS; match surrounding code; touch only what the task needs).
3. **Validate** against the real system — evidence over assertion; test the negative case.
4. **Review** in a fresh context (code-reviewer/verifier) — never self-approve.
5. **Finalize** — `create_memory` durable facts back to the plane (one atomic fact, tag the project, NEVER secrets); zero pending tasks; report with evidence.

**External actions** go through Connect: `list_apps`/`search_actions` → `get_action_guide` → `execute_action`; reads are free, mutations need explicit user intent. **Fleet-scale or long-running agent work** runs on Cluster; memory (not chat) is the handoff between local and cluster agents.
<!-- END DELEGATE-PLANES -->
