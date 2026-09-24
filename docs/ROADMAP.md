# Roadmap

## Phase 0 — Discovery & architecture (done)

Reviewed the existing Streamlit tool, decided on multi-tenant SaaS + Azure +
schema-per-tenant Postgres + FastAPI/Next.js + Clerk + fixed pipeline +
Claude-powered "talk to your data" agent.

## Phase 1 — Foundations + first vertical slice (in progress)

- 1a. Repo scaffolding: FastAPI backend, Next.js frontend, Postgres + Redis
  via docker-compose, Alembic migrations, Clerk auth wiring, Dockerfiles.
- 1b. Multi-tenancy core: `Tenant` model (mapped to a Clerk Organization),
  schema-per-tenant provisioning, `Project`/`Stage` model encoding the fixed
  pipeline and its locking rules.
- 1c. First pipeline slice ported end-to-end:
  - **Load Data** (done) - Mandanten Initial Load: parse/standardize/clean,
    full-replace into the tenant's `mandanten` table, marks the stage done.
    Delta Upload and the other reference tables the original app loads
    (Auftraege, Rollen, Klammertabelle, Verbundene_Parteien, Branchen,
    Mandant_Gegner, Lieferanten, UserCode) are deferred to Phase 2, ported
    alongside the stages that actually consume them.
  - **Address Cleansing - Adress-Analyse (Address field check) + Nacharbeit**
    (done) - `check_addresses` ported in full (placeholder text, legal-form/
    contact-info-in-address, too-long/short, missing house number, city/PLZ
    text embedded in the address), writing to a `junk_address` table;
    Nacharbeit accepts Hoch/Mittel-confidence proposals into `mandanten`.
    **Deferred, each its own follow-up**: the **Referenzdaten** stage
    (curated PLZ_RULES + optional GeoNames import) and the PLZ/City checks
    that depend on it (`check_zipcodes`, `check_city_region`); the
    Claude-based correction step for KONTAKTINFO/RECHTSFORM/ADRESSE_ZU_LANG
    findings (pairs with 1d below); **Zerlegung** (splitting a corrected
    address into SAP fields STREET/HOUSE_NUM1/STR_SUPPL1-3/BUILDING); and
    **Datenbank-Split** (quarantining "infected" records linked to bad
    addresses).
  - Also fixed along the way: `Mandant`/`JunkAddress` now carry a
    `project_id` (a tenant can run several migration projects, unlike the
    original app's one-workspace-per-client model - initially missed when
    Load Data was built, caught and fixed before Address Cleansing could
    inherit the same gap).
- 1d. Chat-with-data agent v1 (done) - Claude API (`claude-opus-5`) via the
  Tool Runner (`client.beta.messages.tool_runner`, `anthropic` SDK 1.8.0),
  hosted in this backend rather than Managed Agents so it runs inside the
  same tenant-scoped session and auth context as everything else. Five
  read-only tools scoped to one tenant+project via closures (the model
  supplies a search query or record id, never the tenant/project boundary
  itself): pipeline status, Address Cleansing findings summary, Mandanten
  search, per-record finding detail, and a Mandanten count. No write tools -
  the agent explains what Accept/Nacharbeit would do rather than doing it.
  Conversation history is kept client-side (plain text turns resent each
  request), not persisted server-side. Verified against the real Claude API
  (a personal key, 30-day expiry - a real project key should replace it
  before this goes further): asked about pipeline status and Address
  Cleansing findings, got a correct, well-synthesized answer with a sharp
  observation the tools didn't hand it directly (findings exist but the
  stage is still locked); multi-turn history round-tripped correctly; and
  asking it to "fix" a finding was correctly refused - it explained what
  accepting would do and pointed back to the UI's Accept button instead of
  pretending to apply it.

## Phase 2 — Port the remaining pipeline stages

One at a time, reusing the pattern established in Phase 1: Datenmodell-
Erweiterung, Geisterobjekte, SAP-CARP, Quality/Report, Tax Cleansing, SAP
Template Migration, RegisterNumber Cleansing, Delete Records.

- **Datenmodell-Erweiterung** (done) - the original's whole reason to exist
  (dynamically adding columns at a precise position) is a SQLite-only
  problem; Postgres just does `ALTER TABLE ADD COLUMN`, so there's no
  dynamic column editor here. What actually carried forward: a proper
  `SapOverridden` bool on `Mandant` (replaces the original's `"Ja"`/`""`
  string flag - set by the not-yet-built SAP-CARP stage, already wired into
  Address Cleansing's population filter, matching `address_common.
  load_population`'s real behavior, which had been silently missing this
  exclusion since Load Data was built). The "add a custom column" feature
  needs no UI at all - `Mandant.extra` already covers it. The page is
  informational (what's reserved, what's planned) plus a mark-done action.
  Verified: flagging a record `SapOverridden` and re-running Adress-Analyse
  correctly dropped it from the checked population and its finding.

- **Geisterobjekte** (done) - finds Mandanten with zero connections to any
  Auftrag, ConnectedParty (VERBUNDENE_PARTEIEN), or MandantGegner row, moves
  them to a `geisterobjekte` table, and restores them on demand. Load Data
  extended with three new reference-table uploads (Auftraege, VERBUNDENE_
  PARTEIEN, MANDANT_GEGNER) feeding this stage. `GhostObject` shares its
  columns with `Mandant` via a `_MandantColumns` mixin instead of
  duplicating the field list. Every relationship check is symmetric - VP and
  MandantGegner each count a Mandant as connected whichever side of the
  relationship it appears on - and every subquery is scoped by `project_id`
  independently, since these reference tables can span a tenant's several
  projects. Ported the consistency check as a small, explicit registry
  (`_CONSISTENCY_REGISTRY`) of "which result tables might still reference a
  now-quarantined ghost", currently covering `junk_address`; adding a
  future stage's result table to the registry is a one-line change.
  **Deferred**: the original's "Report pro User" Excel export (needs
  KLAMMERTABELLE + USERCODE, neither ported yet) and its auto-discovery of
  unregistered result tables (doesn't translate to typed Postgres models -
  the explicit registry is the intended replacement). No separate
  ID-tracking table either - `geisterobjekte` rows carry their own
  `project_id`/`IDParty`, which is enough here since there's no need to
  remember an object was *ever* a ghost after it's restored.
  Verified against a deliberately designed 6-record dataset, one record per
  relationship path (via Auftrag, via VP as IDParty, via VP as
  IDParty_Related, via MandantGegner as Client, via MandantGegner as
  Opponent, and one truly isolated record): quarantine correctly moved only
  the isolated record, leaving the other five in `mandanten`; restore moved
  it back and correctly skipped a ghost whose IDParty had since reappeared
  via a fresh Load Data upload. The consistency check was verified
  end-to-end too: flagged a Mandant via Address Cleansing, quarantined it as
  a ghost, and confirmed the check reported the now-stale `junk_address` row
  with the correct count and hint.

## Phase 3 — Productionization

Azure deployment (Container Apps, Azure DB for PostgreSQL, Azure Cache for
Redis, Blob Storage), logging/metrics/error tracking, audit logging,
security hardening.

## Phase 4 — Sellability polish

Billing/subscription plans, per-tenant usage limits, onboarding flow,
Excel/Parquet export parity with the old tool, load testing.

## Phase 5 — Future

Configurable (non-fixed) pipelines, single-tenant on-prem/VPC packaging for
customers with strict data-residency requirements, expanded agent
write-actions with approval workflows.
