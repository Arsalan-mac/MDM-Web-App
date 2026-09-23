# Architecture

## Context

This product replaces a single-user Streamlit tool (`03-cleansingcode`) used
to clean client master data ahead of an SAP migration: addresses, tax
numbers/VAT, company register numbers, and a "ghost object" /
quarantine-on-split workflow. That tool stored everything in a local SQLite
file per workspace folder and had no real multi-user, multi-tenant, or API
layer. This project rebuilds it as a sellable, multi-tenant SaaS product.

## Decisions

- **Multi-tenant SaaS**, built so a tenant can later be spun off into a
  single-tenant deployment if a customer requires strict data residency.
- **Tenant isolation: one Postgres schema per tenant**, not a shared-table
  `tenant_id` column. A schema-per-tenant model is more scalable towards
  becoming enterprise-friendly, and makes the LLM agent's data access
  boundary structural rather than a query filter that could be missed.
  A `public` schema holds cross-tenant data: `tenants`, `tenant_users`.
- **Backend: FastAPI (Python)**, so the existing pandas/sqlite cleansing
  logic can be ported into a plain `app/cleansing/` package of functions
  instead of being rewritten in another language.
- **Frontend: Next.js + TypeScript**, talking to the backend over REST
  (+ a websocket/polling channel for background job progress and the chat
  agent stream).
- **Auth: Clerk.** A Clerk **Organization** maps 1:1 to a **Tenant**; a
  Clerk **User** maps to a `tenant_users` row. The backend verifies Clerk's
  JWT (JWKS) on every request rather than trusting client-supplied tenant
  IDs.
- **Background jobs: Arq + Redis.** Long-running work (address analysis, tax
  validation, the DB-split) runs as jobs, not inline in a request.
- **Pipeline: fixed for v1**, mirroring the existing app's stage order and
  locking rules (each `Stage` unlocks only once its prerequisite stage is
  marked done). Configurable pipelines are a Phase 5 idea, not v1.
- **Hosting: Azure** — Container Apps (backend, worker, frontend), Azure
  Database for PostgreSQL (flexible server), Azure Cache for Redis, Blob
  Storage for uploads/exports.
- **"Talk to your data" agent**: Claude API (`claude-opus-5`) with tool use,
  hosted inside the backend (not Managed Agents) so it shares the same
  tenant-scoped DB connection and auth context as the rest of the app.
  - Tools are curated, parameterized functions scoped to one
    tenant+project (e.g. `get_pipeline_status`, `get_junk_address_summary`,
    `search_records`, `explain_confidence`) — **the model never executes
    raw SQL** against a tenant schema.
  - The agent is **read-only by default**. Any proposed data change is
    returned as a suggestion the user must explicitly confirm in the UI;
    the agent never calls a write tool unprompted.

## Data model (Phase 1)

- `public.tenants` — one row per customer organization (Clerk org id, name,
  Postgres schema name, plan/status).
- `public.tenant_users` — Clerk user id ↔ tenant id ↔ role.
- Per-tenant schema:
  - `projects` — one row per migration project.
  - `stages` — one row per pipeline stage per project (fixed set from
    `app/models/tenant.py::PIPELINE_STAGES`), tracking `status`
    (`locked` / `in_progress` / `done`) and unlock ordering.
  - Stage-specific tables are added as each stage is ported (Phase 1c
    starts with `mandanten`, `junk_address` for Load Data + Address
    Cleansing).

## Why not shared tables + `tenant_id`?

It's the more common multi-tenant pattern and cheaper to operate at very
large tenant counts, but two things pushed towards schema-per-tenant here:
the source data is sensitive pre-migration PII (addresses, tax/VAT IDs), and
an LLM agent now has query access to it. A forgotten `WHERE tenant_id = ?`
in either the app code or a future tool becomes a cross-customer data leak;
schema isolation makes that bug class structurally harder to introduce, and
it's the natural boundary if a customer later needs their own
single-tenant deployment.
