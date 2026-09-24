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

- **Tax Cleansing - Steuernummer-Cleansing (Fiscal Code) phase** (done) -
  ported from tax_cleansing_module.py's remaining two Steuernummer-
  Cleansing sub-tabs: `run_fiscal_code_analysis` (2-stage syntax + country/
  entity-type pattern check) and the Regelwerk rules editor (list/upsert/
  reset backed by the FISCAL_RULES table). The ~460-line, 90-country
  `_get_sap_fiscal_rules()` seed dict was extracted programmatically
  (`ast.literal_eval` on the original function's return value, verified to
  match byte-for-byte) into `app/cleansing/fiscal_rules_seed.py` rather
  than retyped by hand - this is real tax-ID validation data, and a
  transcription slip in a regex is a correctness bug a human reviewer is
  unlikely to catch by reading a diff.
  **Scope decisions**: `FiscalRule` is scoped per-project (like
  SapStammdaten/FieldMapping), lazily seeded from the code defaults on
  first read - this codebase has no tenant-wide shared-config concept, and
  a Project is the closest match to the original's one-ruleset-per-
  workspace scope. The official "SAP Tax Number Categories" reference
  list shown read-only in the original's Regelwerk tab isn't ported here -
  it exists solely to back TAXTYPE validation in Migration Preparation
  (confirmed by reading `validate_taxtypes_against_categories`, which
  checks `TAX_MIGRATION_RESULT`, not FiscalCode), so displaying it in this
  phase would be a UI element with nothing yet connected to it; it lands
  with Migration Preparation instead. Excel import/export for the rules
  editor is deferred, consistent with every other stage's Excel-export
  deferral so far - the editor supports view/edit/reset without it. The
  editor's filter (country search) only affects what's *displayed*, not
  what's saved - the original's Streamlit data_editor conflated the two
  (editing happens on the filtered view, so "Save" only persists whatever
  rows the filter happened to show), which reads as an artifact of that
  widget rather than an intentional design worth reproducing.
  Verified end-to-end against real Postgres/Clerk with an 8-Mandant
  dataset: GET auto-seeded exactly 270 rules (90 countries x 3 entity
  types); a 10-digit German FiscalCode validated against the seeded DE
  ORG rule while a too-short and a wrong-length value were correctly
  flagged (with the exact expected description text echoed back as the
  junk reason); an Italian Codice Fiscale validated against its primary
  regex and an 11-digit value validated via its alias regex; a record from
  a country with no seeded rule was correctly left unflagged rather than
  junked; upserting a looser DE ORG regex immediately changed the next
  analysis run's result (the previously-flagged record passed); and
  resetting reverted to the code defaults and restored the original junk
  finding exactly.

- **Tax Cleansing - Migration Preparation phase** (done) - ported from
  tax_cleansing_module.py's third and final tab: `_run_vat_migration_if_
  requested` and `_run_steuer_migration_if_requested` (build `TAX_MIGRATION_
  RESULT` rows from whichever track's clean population - CH/NO/RU pre-
  cleaning, EU/Non-EU region-based `VAT_MAPPING` lookup, Canada's pattern-
  based special case, FISCAL_RULES sap_code lookup for Steuernummer),
  `validate_taxtypes_against_categories` (UNKNOWN/OBSOLETE/COUNTRY_MISMATCH/
  VAT_CATEGORY_HINT/KEY_COLLISION checks against the official SAP Tax Number
  Categories list), `_suggest_collision_code`, and the TAXTYPE_REMAP/
  TAXTYPE_ROW_FIX correction tables. The 377-entry SAP category list
  (`_SAP_TAX_CATEGORIES_SEED`) and the 58-entry `_VAT_MAPPING_SEED` were
  both extracted programmatically (`ast.literal_eval`, verified byte-for-
  byte) into `app/cleansing/sap_tax_categories.py` and `vat_mapping_seed.py`
  - same reasoning as the fiscal-rules seed: this is reference tax data,
  not something to retype by hand.
  **Scope decisions**: Canada's special-case TAXTYPE assignment
  (`_assign_ca_code` - RT-suffixed accounts keep the full value under CA1;
  other R[A-Z] accounts and bare 9-digit Business Numbers reduce to their
  9-digit BN under CA2) is ported faithfully even though CA2 isn't itself in
  the official SAP category list - the validation step correctly flags that
  as UNKNOWN, which is the original algorithm's real (if debatable) behavior,
  not a porting bug; see the live-test note below. `SAP-Abgleich` (`run_sap_
  taxtype_sync`, direct sync against a connected SAP system) is dropped
  entirely rather than deferred - reading the original's own current tab-
  rendering code confirms this feature is already hidden/disabled in the
  upstream app itself, so there is no live behavior to port. As with every
  other stage, the original's extensive per-region/per-country/per-entity
  Excel exports are deferred, consistent with the established Excel-export
  deferral pattern; migration logic and TAXTYPE assignment are ported in
  full, only file-delivery mechanics are dropped. VAT_MAPPING is a project-
  scoped, user-editable table (list/save/reset), matching FISCAL_RULES'
  precedent. Both migration tracks recompute their junk population fresh via
  the existing stateless VAT/FiscalCode analysis functions rather than
  depending on a separately persisted junk table, avoiding a staleness bug
  class that isn't present in this codebase to begin with.
  Verified end-to-end against real Postgres/Clerk with a 9-Mandant dataset
  covering DE/FR/IT/ES/NL VAT, a splittable and an unsplittable Russian VAT,
  and both Canadian patterns (RT and bare/RC BN): VAT migration produced the
  expected 10 result rows (9 Mandanten, RU's INN/KPP split into 2); a DE
  FiscalCode migrated to the correct Steuernummer SAP code while the other 8
  empty FiscalCodes were correctly excluded; the baseline validation run was
  clean except for the expected CA2-not-in-category-list UNKNOWN finding
  (see scope note above); four TAXTYPE_REMAP entries were added and, on
  re-migration, correctly produced one UNKNOWN, one OBSOLETE, one COUNTRY_
  MISMATCH, and three VAT_CATEGORY_HINT findings (matching the validation
  mask's exact logic, including that an obsolete code still independently
  triggers a VAT-category hint); the collision-suggestion endpoint correctly
  proposed a country's official VAT code for a mismatched VAT row; a
  TAXTYPE_ROW_FIX entry was used to deliberately force two TAX_MIGRATION_
  RESULT rows for the same IDParty to the same TAXTYPE, which the validator
  correctly flagged as a KEY_COLLISION naming both rows, and the collision-
  suggestion endpoint correctly proposed reverting to the Steuernummer
  category; deleting the row-fix and remaps and re-running both migrations
  confirmed every finding count returned to its clean baseline; and the VAT
  Mapping editor's edit/save/reload/reset round-trip persisted and reverted
  a region change exactly as expected.
  This completes Tax Cleansing (all three tabs: VAT-Cleansing,
  Steuernummer-Cleansing, Migration Preparation).

- **Address Cleansing - Zerlegung** (done) - ported from sap_address_
  module.py: splits `Mandant.Address` into SAP's ADRC target fields
  (STREET/HOUSE_NUM1/STR_SUPPL1-3/BUILDING) via a staged regex parser (T0
  PO box, T1 house number at the end, T2 at the front, T3 comma-segment
  best-effort for complex cases), with a Claude Haiku batch fallback for
  addresses the regex can't confidently split - same architecture as
  SAP-CARP's Name Splitting (regex first, LLM only for the genuinely hard
  cases, LLM output validated against the original text - every digit and
  token must trace back to the source address, nothing invented or
  translated - before it's trusted). All length limits (STREET 60,
  STR_SUPPL 40 each, HOUSE_NUM1 10, BUILDING 20) are enforced centrally in
  code for both the regex and LLM paths, never left to the LLM.
  **Why this got built now**: SAP Template Migration's ADRC sheet needs
  these fields, and Zerlegung was the original's own upstream step that
  populates them - deferred as a follow-up when Address Cleansing was
  first ported (see that entry above), picked up now as a genuine
  prerequisite rather than skipped.
  **Scope decisions**: the proposal/review/accept workflow follows Address
  Cleansing's own Nacharbeit precedent - no old-value guard or persisted
  change log (no concurrent editors here yet, same call already made for
  Nacharbeit) - but keeps the original's confidence-tiered bulk "Übernahme"
  (accept all Hoch, or Hoch+Mittel, in one call) rather than Nacharbeit's
  one-row-at-a-time accept, since Zerlegung's own UX was always bulk-first
  in the original app. The LLM result cache table and `calibrate_against_
  sap_streets` (a QA tool comparing parsed streets against a real SAP
  street-name export, with no ported stage consuming its output) are not
  carried over - an in-memory cache per run is enough, matching how SAP-
  CARP's Name Splitting already diverged from the original's cross-run
  caching table.
  Verified with 19 unit tests covering every parse tier (T0-T3), the
  length-enforcement cascade, and `spell_out_street`, plus a live run
  against real Postgres/Clerk: a clean DE address (T1, Hoch), a US
  number-first address (T2, Hoch), a PO box (T0, Hoch), and a c/o-prefixed
  address (Mittel) all parsed to their exact expected fields; an address
  Adress-Analyse itself had already flagged (KONTAKTINFO) and one it had
  independently flagged for having no house number (KEINE_HAUSNUMMER) were
  both correctly excluded from the candidate set - the same "skip rows
  with an open manual JUNK_ADDRESS finding" rule the original enforces;
  accepting Hoch-confidence proposals updated exactly those 3 Mandant
  records and removed them from the list; accepting the remaining Mittel
  proposal with "spell out" enabled wrote the spelled-out street form
  ("Bahnhofstr." -> "Bahnhofstraße") - confirmed by querying Postgres
  directly, not just the API response.

- **SAP Template Migration - BUT000-General + ADRC-Address slice** (done) -
  ported from sap_template_module.py, the largest module ported so far
  (4287 lines - bigger than Tax Cleansing). It generates the actual SAP
  Business Partner master-data migration rows from Mandanten, driven by a
  mapping-spec DSL defined in `mapping_specs/*.map` text files. This first
  slice covers the two sheets that need neither a materialized base table
  nor the SPLIT/TRUNCATE overflow policies - BUT000-General (partner
  master data: name, org/person flag, title, legal form, archiving flag)
  and ADRC-Address (the address itself, plus a "Fehlerhafte Anschrift"
  comment for partners Adress-Analyse flagged).
  **Scope decisions**:
  - The original's mapping-spec DSL is parsed from text at runtime, but
    only because the `.map` files are meant to be hand-edited outside the
    app (their own header comments say "Bearbeiten z. B. in VS Code") and
    then re-ingested - there is no in-app text editor for them, confirmed
    by reading every UI code path in the original's three tabs. That's
    exactly the FISCAL_RULES/VAT_MAPPING/SAP_TAX_CATEGORIES pattern this
    app already uses for reference config edited as code, not through the
    UI - so instead of reimplementing a runtime DSL parser nothing needs,
    the two sheets' mappings were hand-encoded as structured Python data
    (`app/cleansing/sap_template_mappings.py`), checked field-by-field
    against the original `.map` files (same target-field order, lengths,
    rule types, conditions).
  - The four materialized-table sheets (BUT100 from Rollen with RLTYP-code
    mapping and role suppression, BUT0ID from RegisterNumber with
    type-sniffing, BUT0IS from Branchen with first-row-per-group ISDEF
    logic, BUT000-Append for populated-attribute partners only) and
    DFKKBPTAXNUM (needs Tax Cleansing's TAX_MIGRATION_RESULT) are deferred
    - each needs its own fan-out-capable builder the 1:1 mapping engine
    can't express, and none blocks proving the engine itself end-to-end.
  - Generation is stateless (recomputed fresh from Mandanten/JunkAddress on
    every call), matching Tax Cleansing's migration/validation endpoints -
    no persisted output table to go stale.
  - REGION has no Mandant column: the original stopped exporting it in
    2026-09-22 (the SAP cockpit rejected the Bundesland codes it used to
    carry) and never populated `Mandanten.REGION` again after that, so
    ADRC's REGION target field maps to a constant empty string instead of
    a dead column.
  - The engine is a plain per-row loop over ORM objects, not pandas
    vectorization - this app's Projects are single-tenant workspaces, not
    the original's 130k+-row shared database, and every other cleansing
    service here already favors a loop over a DataFrame pipeline.
  - Date reformatting (`Format: YYYYMMDD` etc.) is ported byte-for-byte
    from the original's `_apply_date_format` regex approach (ISO takes
    precedence over day-first, month 1-12/day 1-31 plausibility check) -
    deliberately not `datetime`-parsing based, since that fails past year
    2262 and mis-guesses mixed formats, exactly the reasoning the original
    documents for avoiding `pd.to_datetime`.
  - Excel export is NOT deferred this time (unlike every other stage so
    far) - one workbook (both sheets + a red-highlighted "Violations"
    sheet) ships in this slice, since a downloadable file is this stage's
    actual purpose; what's deferred is the batch multi-country/CSV/
    anonymized export from the original's Export tab, not export itself.
  - Two Mandant column-plumbing bugs were caught and fixed while wiring
    this up, both pre-existing gaps this slice's data finally exercised:
    `STANDARD_MANDANT_COLUMNS` (the Load Data upload whitelist deciding
    typed-column vs. `extra`) didn't list the four new source fields
    (AddedDate, RoedlCompanyNumber, TitleCode, LegalFormCode), so uploaded
    values for them silently landed in `extra` and never reached the
    typed columns SAP Template Migration reads; and SAP-CARP's Field-
    Mapping overwrite step resolved its target column by DB column *name*
    but wrote via `setattr` (which needs the Python attribute *key*) -
    harmless while every column's name and attribute matched, but Name1-4's
    explicit `"Name 1"`-style column name (kept to match the SAP mapping
    spec's own field reference) would have silently no-opped instead of
    writing the field. Both fixed (`app/cleansing/constants.py`,
    `_MANDANT_COLUMN_TO_ATTR` in `sap_carp_service.py`) before they could
    ship as live bugs.
  - Name 1-4 (SAP-CARP's CompanyName distribution) were promoted from
    `Mandant.extra` to typed columns now that BUT000-General reads them
    back, same rule FirstName/LastName followed earlier: `extra` until a
    stage actually consumes a field, typed once one does.
  Verified with 25 unit tests (every rule type, the date-format regex
  cascade including implausible-date rejection, overflow flagging, the
  JUNK_ADDRESS join) and a full live e2e run against real Postgres/Clerk
  through the *entire* upstream pipeline - Load Data, SAP-CARP's Name 1-4
  distribution and Name Splitting, Adress-Analyse, and Zerlegung - then
  SAP Template Migration itself: an organisation with a Rödl company
  number correctly got BU_GROUP=ZICO and its LEGAL_ENTY code, an inactive
  organisation got XDELE=X, a natural person got BPKIND=1/TITLE from its
  own TitleCode/name-split FirstName+LastName while NAME1_ORG correctly
  stayed empty (name distribution only touches organisations), a partner
  with an open Adress-Analyse finding got ADRC's "Fehlerhafte Anschrift"
  comment and no Zerlegung-derived address fields, a clean organisation's
  Zerlegung-accepted STREET/HOUSE_NUM1 and reformatted AddedDate
  (`2026-01-15 08:00:00.000` -> `20260115`) came through exactly, a
  deliberately oversized legal-form code was correctly flagged as a FLAG
  overflow violation end-to-end, and the downloaded workbook opened with
  the exact three expected sheets, red-highlighted overflow cells, and a
  populated Violations sheet.

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
