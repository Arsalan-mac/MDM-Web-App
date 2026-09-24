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
- 1d. Chat-with-data agent v1: Claude API tool use, a handful of curated
  read-only tools scoped to one tenant+project, chat panel in the UI.

## Phase 2 — Port the remaining pipeline stages

One at a time, reusing the pattern established in Phase 1: Datenmodell-
Erweiterung, Geisterobjekte, SAP-CARP, Quality/Report, Tax Cleansing, SAP
Template Migration, RegisterNumber Cleansing, Delete Records.

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
