# Enabling the claude.ai (browser) custom connector via Google OAuth

**Goal:** let `memory.delegate.ws` be added as a custom connector in the claude.ai
browser app, which requires an OAuth discovery flow (the static bearer alone can't
satisfy it).

**Key finding:** Forgetful runs **FastMCP v3.2.2**, which ships native OAuth
(Dynamic Client Registration, PKCE S256, `/authorize`, `/token`, `/.well-known/*`,
JWKS). The Google/GitHub providers are `OAuthProxy` subclasses that provide that
whole surface AND proxy the human login upstream. **No new code is required** — only
configuration + three out-of-repo steps. The earlier "2–3 day TS shim port" plan is
obsolete.

The config lives in `docker/.env.example` under **Option 4b** (env-var only; the
factory is already implemented at `app/config/auth.py:58` `_build_google`).

---

## The three steps that are NOT in this repo (all required, all manual)

### 1. Google Cloud Console — add the redirect URI
On the **DelegateMail** Google OAuth client, add an Authorized redirect URI:

```
https://memory.delegate.ws/auth/callback
```

- Client ID: `182502174800-aggkqqh4747cccdutqf1hp16rep6pobq.apps.googleusercontent.com`
- Google Cloud project: `gen-lang-client-0089533980`
- Console path: **APIs & Services → Credentials →** that OAuth 2.0 Client ID →
  **Authorized redirect URIs → Add**
- The path `/auth/callback` is FastMCP `GoogleProvider`'s default `redirect_path`
  (verified in `.venv/.../fastmcp/server/auth/providers/google.py:263`). If it is not
  added exactly, Google returns `redirect_uri_mismatch`.
- Web-client redirect URIs are **not** editable via `gcloud` — this is a manual
  console action (confirmed pattern, memory 4105).

This client is already shared across surfaces (DelegateMail, SysOp console), so adding
one more redirect URI does not disturb existing logins — it only adds.

### 2. Supply CLIENT_ID / CLIENT_SECRET into the DEPLOYED environment
Source values (do **not** copy the secret into any tracked file):

- From `/Volumes/Projects/Delegate Mail/.env`: `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`
  (also present in `Delegate/.env`).

Set on the deployed Forgetful service:

```
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.google.GoogleProvider
FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID=<AUTH_GOOGLE_ID>
FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET=<AUTH_GOOGLE_SECRET>
FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL=https://memory.delegate.ws
FASTMCP_SERVER_AUTH_GOOGLE_REQUIRED_SCOPES=openid,https://www.googleapis.com/auth/userinfo.email
```

`BASE_URL` must be the public tunnel URL — it becomes the OAuth **issuer** and must
match byte-for-byte or RFC 8414 discovery validation fails.

### 3. core2 / Caddy — exempt the OAuth paths from the static-bearer gate
claude.ai must reach these **unauthenticated** (a bearer-401 there breaks the SSO
screen — this is the exact "SSO screen not working" symptom seen before):

```
/auth/callback
/authorize
/token
/register
/.well-known/*
```

A 401 on the protected-resource path must carry `WWW-Authenticate: ... resource_metadata`
(FastMCP emits this) — not the Caddy static-bearer 401.

---

## Do not break existing access

Turning on `FASTMCP_SERVER_AUTH` changes how the server authenticates for **all**
callers. Today Claude Code / CLI use the static bearer in `~/.claude/mcp.json`
(and `~/.claude.json`). Confirm the intended end state before flipping:

- If the **Caddy static-bearer gate stays in front** for non-OAuth paths (the `/mcp`
  calls Claude Code makes), CLI access continues to work and OAuth is additive for the
  browser. This is the intended shape (exempt only the OAuth paths in step 3).
- If instead the FastMCP layer itself starts requiring OAuth on `/mcp`, the static
  bearer stops working and every CLI/agent config must migrate to an OAuth token.
  **Not recommended** — it breaks the whole fleet's memory access at once.

Decide this explicitly; it is the highest-blast-radius part of the change.

---

## Verify after deploy (evidence, not assumption)

From any machine (no bearer needed for discovery once step 3 is done):

```bash
curl -s https://memory.delegate.ws/.well-known/oauth-protected-resource | jq .
curl -s https://memory.delegate.ws/.well-known/oauth-authorization-server | jq .
```

Expect JSON with `issuer=https://memory.delegate.ws`, an `authorization_endpoint`,
`token_endpoint`, `registration_endpoint`, and `code_challenge_methods_supported:["S256"]`.
Both currently return **404** (no OAuth deployed) — 200 with that JSON is the success signal.

Then in claude.ai: **Settings → Connectors → Add custom connector**, URL
`https://memory.delegate.ws/mcp`, leave the OAuth Client ID field empty (claude.ai
self-registers via DCR). Success = a Google consent screen, then the 3 Forgetful tools
listed.

---

## Provenance
- FastMCP version + native-OAuth capability: `pyproject.toml:24`; `app/config/auth.py:58`
  (`_build_google`); `.venv/.../fastmcp/server/auth/providers/google.py:237-345`
  (`base_url`, `redirect_path` default `/auth/callback`).
- Server already built with `auth=build_auth_provider()`: `main.py:111`.
- DelegateMail Google client / redirect-URI-is-manual: memory plane (SysOp reuse
  2026-08-03; `redirect_uri` manual-add gotcha, memory 4105).
- claude.ai connector = static-bearer-incompatible / needs OAuth discovery: memory
  31626 (verified 2026-08-05).
