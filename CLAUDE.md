@./AGENTS.md

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
