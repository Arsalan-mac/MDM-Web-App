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
  **Bug fixed later (found while taking product screenshots)**: creating a
  new Clerk Organization via the `OrganizationSwitcher` never called
  `POST /tenants/provision` - nothing in the frontend did, so a brand-new
  org hit a dead end ("This organization has not been provisioned yet")
  with no way to recover short of calling the API directly. Fixed by having
  the dashboard call `provisionTenant` (already idempotent) itself before
  every projects fetch - covers org creation and switching to any org
  created elsewhere, not just the one creation path. Surfaced a second,
  related bug in the same fix: Clerk auto-generates org slugs with hyphens
  (e.g. `acme-corp-1790269034013731139`), but the backend's tenant-slug
  validator only allows `[a-z0-9_]` (it becomes an unquoted Postgres schema
  name, so this is a hard security boundary, not cosmetic) - every prior
  manual test of this flow had quietly sidestepped it by hand-picking an
  underscored slug instead of using Clerk's real one. Fixed with a
  `sanitizeTenantSlug` helper (hyphens/other chars -> underscore) in the
  frontend rather than loosening the backend's validation. Verified against
  a real, never-provisioned Clerk org with its actual hyphenated slug: the
  dashboard now provisions it automatically (schema created, Tenant row
  correctly slugified) and loading it twice doesn't create a duplicate.
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

- **SAP-CARP-Ueberschreibung** (done) - overwrites Mandanten fields from an
  uploaded SAP export via a Field-Mapping file (`Mandanten` column,
  `SAP-Allgemeine Stammdaten` column, optional `IsOrganisation` condition),
  distributes CompanyName into SAP's Name 1-4 export slots, and splits
  natural-person names into FirstName/LastName (nameparser rules, Claude
  Haiku for the ambiguous 3+-token/no-comma case). Two scope calls, both
  because Field-Mapping/SAP exports don't carry a fixed column set the way
  Mandanten's own upload does:
  - A Field-Mapping row targeting one of Mandant's typed columns overwrites
    it directly; targeting anything else (e.g. the Name 1-4 slots, which no
    ported stage reads back) lands in `Mandant.extra` instead - the same
    rule the reference-table loaders already follow, rather than growing
    the typed column set for fields nothing consumes yet. FirstName/
    LastName *did* get typed columns, since this same stage's own cleanup
    query reads them back.
  - The uploaded "SAP-Allgemeine Stammdaten" file's columns are arbitrary
    (whatever Field-Mapping references by name), so each row is kept as a
    JSONB dict (`SapStammdaten.data`) rather than typed columns, with only
    the resolved join key (`IDParty`, falling back to `Ext. Partnernummer`
    on older exports) indexed separately.
  The "erledigt" flag that unlocked the rest of the original app's nav is
  just this project's `sap_carp` Stage reaching status "done" here - no
  separate settings table needed, since every stage already has a lock/
  unlock mechanism the original's single-workspace app didn't.
  **Deferred**: the SAP-GP-Mapping and SAP-Steuernummern upload slots (the
  original's own Upload tab tracks them, but nothing overwrite-related
  consumes them; GP-Mapping isn't consumed by any ported stage yet, and
  Steuernummern belongs with Tax Cleansing - both get their upload wired in
  alongside the stage that actually needs them, same pattern Load Data's
  other reference tables followed until Geisterobjekte needed them).
  Verified end-to-end against real Postgres/Clerk with a 6-Mandant dataset:
  two records present in an uploaded SAP-Allgemeine-Stammdaten file (one
  Field-Mapping row unconditional, one gated on `IsOrganisation = 1`, one
  targeting a non-typed column, one referencing a SAP column absent from
  the upload) - the overwrite correctly updated the typed columns, wrote
  the non-typed target into `extra`, left the record with the missing SAP
  column untouched, flagged only the two matched records `SapOverridden`,
  and the status endpoint correctly listed the missing SAP column as a
  warning. CompanyName distribution matched `textwrap.wrap`'s own output
  exactly for both a 2-word and a 4-word company name at a small chunk
  size. Name Splitting was verified across all four rule-based methods
  (comma format, 2-token, single-token "unklar", plus a real Claude Haiku
  call for a 3-token name with no comma - correctly split "Hans Peter
  Mueller" into "Hans" / "Peter Mueller") and its own cleanup action
  correctly emptied CompanyName only for the three records that had just
  been given a FirstName/LastName.

- **Quality Analysis** (done) - seven independent data-quality checks,
  ported from `app_analysis_ui`'s Mandanten-DQ and Auftraege-DQ tabs: a
  DB-Bereinigung value cleanup, fuzzy duplicate detection (TF-IDF +
  Nearest Neighbors, blocked by country/ZIP prefix), a RegisterNumber
  junk check, Email/Website/Phone/Fax format checks, a per-attribute
  completeness report, date standardization (DateFounded/LiquidationDate/
  RegisterCourtDate to YYYY-MM-DD), and an Auftraege ID-Project conflict
  check. Unlike Address Cleansing, none of these have a persistent
  "Nacharbeit" review queue in the original app - each is "run it, see the
  result" - so nothing here gets its own results table; every check
  recomputes on each call and the frontend just displays the latest
  response. The original's local-Excel exports (`save_to_local_drive`,
  the consolidated `DQ_Quality_Report.xlsx`) aren't ported, consistent
  with every other stage's Excel-export deferral so far.
  **Scope decisions**:
  - **Missing ID is not ported at all** - the original's whole reason to
    exist (Mandanten with no IDParty) is structurally impossible here:
    `Mandant.IDParty` is a NOT NULL primary-key column
    (app/models/tenant.py), so such a row can never be inserted in the
    first place. A check that can only ever return zero isn't worth
    building.
  - The completeness check's ~48-column target list (mirrors SAP BUT000's
    real field set) reads whichever of Mandant's typed columns match, and
    falls back to `extra` for the rest (GroupName, BirthDate, TitleCode,
    etc.) - the same typed-vs-extra split every prior stage has used, just
    applied at read time here instead of write time.
  - `RegisterNumber`/`RegisterCity`/`RegisterCourtKindCode` and Auftrag's
    `ProjectName`/`AddedDate`/`ServiceName` got promoted to typed columns
    since this stage's own checks query/group by them directly.
    `register_number_issues` (the junk-detection rules) was ported into
    its own `app/cleansing/register_checks.py` rather than inline, so the
    future RegisterNumber Cleansing stage can import the same rules as its
    "Stufe 1", matching the original's single-source-of-truth comment.
  Verified end-to-end against real Postgres/Clerk with a 6-Mandant + 3-
  Auftrag dataset: the RegisterNumber check correctly flagged a dummy
  sequence, a digit-repetition, and a placeholder value (and correctly
  left an empty value out of both the junk and valid counts); the
  communication check correctly caught a malformed email/URL/phone number
  while leaving clean ones alone; the completeness check correctly showed
  0% fill for an `extra`-only column (GroupName) that no test record set;
  date standardization correctly resolved both an mm/dd/yyyy value and a
  dd.mm.yyyy value to the same real calendar date and persisted the
  rewrite; the fuzzy check correctly matched two near-duplicate company
  records ("Mueller Handels GmbH" / "Muller Handels GmbH", same address)
  at 84.5% similarity while leaving unrelated records alone; the DB
  cleanup correctly blanked an exact-match junk value ("-") in Address;
  and the Auftraege ID-Project check correctly flagged the one IDParty/
  ProjectName/AddedDate group with two different ServiceNames while
  leaving the unambiguous group alone.

- **Tax Cleansing - VAT-Cleansing phase only** (done) - ported from
  tax_cleansing_module.py's 💶 VAT-Cleansing tab: `run_unified_vat_analysis`
  (empty-VATNumber backfill from ViesNumber, Swiss/Norwegian pre-cleaning,
  Russian INN/KPP compound splitting, a syntax junk check, then pattern
  validation against a ~70-country regex table) and `run_vat_duplicate_
  analysis`. Steuernummer-Cleansing (Fiscal Code, backed by a ~460-line
  SAP fiscal-rules reference table) and Migration Preparation (TAXTYPE
  validation/remap/collision-fix workflow, SAP sync) are the original's
  other two tabs on this same page - deliberately deferred as separate,
  larger follow-up passes rather than bundled in here (this module is
  ~3.4k lines, by far the largest ported so far, and the three tabs are
  independent workflows). `ViesNumber` was promoted to a typed Mandant
  column since this stage reads and writes it directly; the pure VAT
  helpers (Swiss/Norwegian/Russian cleaning, the country regex table)
  live in their own `app/cleansing/vat_rules.py`, same reasoning as
  `register_checks.py` - reusable by Migration Preparation later, and
  independently unit-testable.
  One correctness improvement over the original: its "does an RU KPP
  split-row's ID make it into the syntax-checked set" step filters by
  `df[PRIMARY_KEY].isin(valid_syntax_ids)` - `IDParty`-based membership,
  not row identity - and since an INN row and its KPP row legitimately
  share the same IDParty, a KPP row can accidentally inherit its INN
  sibling's pass/fail syntax result instead of being judged on its own
  value. This port tracks each check entry independently instead, so the
  INN and KPP halves of a split value are always judged on their own
  merits.
  Verified end-to-end against real Postgres/Clerk with a 12-Mandant
  dataset covering every path: a clean German VAT; a too-short syntax
  failure; a pattern mismatch (7-digit value doesn't fit DE's 9-digit
  format); Swiss pre-cleaning (`CHE-123.456.789 MWST` -> validates);
  Norwegian pre-cleaning (bare 9 digits -> `NO...MVA` -> validates); a
  valid Russian INN/KPP split; an invalid split (9-digit INN fails RU's
  10/12-digit rule, 5-digit KPP fails the 9-digit rule - both correctly
  flagged independently); a 2-slash Russian value correctly junked
  immediately as unsplittable; a ViesNumber backfill that then validated
  clean and was correctly persisted to `mandanten`; and two records
  sharing one VAT number under different formatting (dashes vs. none)
  correctly matched as duplicates. The quality-report Organisation/
  Natuerliche-Person split (9 vs. 3 records, exact valid/junk/empty
  counts) matched a hand-computed expectation exactly.

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
