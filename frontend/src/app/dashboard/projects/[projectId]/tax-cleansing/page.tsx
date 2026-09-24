"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import {
  deleteTaxtypeRemaps,
  deleteTaxtypeRowFixes,
  getCollisionSuggestion,
  getFiscalRules,
  getTaxtypeRemaps,
  getTaxtypeRowFixes,
  getTaxtypeValidation,
  getVatMapping,
  resetFiscalRules,
  resetVatMapping,
  runFiscalCodeAnalysis,
  runSteuerMigration,
  runVatAnalysis,
  runVatDuplicateCheck,
  runVatMigration,
  saveFiscalRules,
  saveTaxtypeRemap,
  saveTaxtypeRowFix,
  saveVatMapping,
  setStageStatus,
  type FiscalCodeAnalysisResult,
  type FiscalRule,
  type MigrationRunResult,
  type QualityReportRow,
  type TaxtypeRemapEntry,
  type TaxtypeRowFixEntry,
  type TaxtypeValidation,
  type TaxtypeValidationFinding,
  type VatAnalysisResult,
  type VatDuplicateRow,
  type VatMappingEntry,
} from "@/lib/api";

type Tab = "fiscal" | "vat" | "migration";
type FiscalSubTab = "analyse" | "regelwerk";

const cell: React.CSSProperties = { border: "1px solid #ccc", padding: "3px 8px" };
const input: React.CSSProperties = { width: "100%", padding: "2px 4px", fontSize: "0.85rem" };

function QualityReportTable({ rows }: { rows: QualityReportRow[] }) {
  if (rows.length === 0) return null;
  return (
    <table style={{ borderCollapse: "collapse", marginTop: "0.75rem", fontSize: "0.85rem" }}>
      <thead>
        <tr>
          {["Typ", "Clients", "Valid", "Junk", "Empty", "% Valid", "% Junk", "% Empty"].map((h) => (
            <th key={h} style={cell}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.type}>
            <td style={cell}>{r.type}</td>
            <td style={cell}>{r.total_clients}</td>
            <td style={cell}>{r.total_valid}</td>
            <td style={cell}>{r.total_junk}</td>
            <td style={cell}>{r.total_empty}</td>
            <td style={cell}>{r.pct_valid}%</td>
            <td style={cell}>{r.pct_junk}%</td>
            <td style={cell}>{r.pct_empty}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FiscalRulesEditor({ projectId }: { projectId: string }) {
  const { getToken } = useAuth();
  const [rules, setRules] = useState<FiscalRule[] | null>(null);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setRules(await getFiscalRules(token, projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load rules.");
    } finally {
      setBusy(false);
    }
  }

  function updateRule(idx: number, patch: Partial<FiscalRule>) {
    setRules((prev) => (prev ? prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)) : prev));
  }

  async function handleSave() {
    if (!rules) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { saved } = await saveFiscalRules(token, projectId, rules);
      setMessage(`Saved ${saved} rule(s).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save rules.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReset() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { rule_count } = await resetFiscalRules(token, projectId);
      setMessage(`Reset to code defaults (${rule_count} rules).`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset rules.");
    } finally {
      setBusy(false);
    }
  }

  if (rules === null) {
    return (
      <button onClick={load} disabled={busy}>
        {busy ? "Loading…" : "Load rules"}
      </button>
    );
  }

  const filtered = rules
    .map((r, idx) => ({ r, idx }))
    .filter(({ r }) => !search || r.country_code.toUpperCase().includes(search.toUpperCase()));

  return (
    <div>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}
      <div style={{ display: "flex", gap: "1rem", alignItems: "center", margin: "0.5rem 0" }}>
        <input
          placeholder="Search country code…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ padding: "0.3rem", width: "12rem" }}
        />
        <span style={{ color: "#666", fontSize: "0.85rem" }}>
          {filtered.length} of {rules.length} rules shown
        </span>
        <button onClick={handleSave} disabled={busy}>
          💾 Save changes
        </button>
        <button onClick={handleReset} disabled={busy}>
          🔄 Reset to code defaults
        </button>
      </div>
      <div style={{ overflowX: "auto", maxHeight: 500, overflowY: "auto", border: "1px solid #eee" }}>
        <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", width: "100%" }}>
          <thead>
            <tr>
              {["Land", "Typ", "SAP Code", "Regex", "Aliases (JSON)", "Description", "Confidence"].map((h) => (
                <th key={h} style={{ ...cell, position: "sticky", top: 0, background: "#f5f5f5" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(({ r, idx }) => (
              <tr key={`${r.country_code}-${r.entity_type}`}>
                <td style={cell}>
                  {r.country_code} / {r.entity_type}
                </td>
                <td style={cell}>{r.sap_code}</td>
                <td style={cell}>
                  <input style={input} value={r.regex} onChange={(e) => updateRule(idx, { regex: e.target.value })} />
                </td>
                <td style={cell}>
                  <input
                    style={input}
                    value={JSON.stringify(r.aliases)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value);
                        if (Array.isArray(parsed)) updateRule(idx, { aliases: parsed });
                      } catch {
                        // ignore until valid JSON
                      }
                    }}
                  />
                </td>
                <td style={cell}>
                  <input
                    style={input}
                    value={r.description}
                    onChange={(e) => updateRule(idx, { description: e.target.value })}
                  />
                </td>
                <td style={cell}>
                  <select
                    value={r.confidence}
                    onChange={(e) => updateRule(idx, { confidence: e.target.value })}
                    style={input}
                  >
                    <option value="HIGH">HIGH</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="LOW">LOW</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MigrationPreparationTab({ projectId }: { projectId: string }) {
  const { getToken } = useAuth();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [vatMapping, setVatMapping] = useState<VatMappingEntry[] | null>(null);
  const [migrationResult, setMigrationResult] = useState<MigrationRunResult | null>(null);
  const [validation, setValidation] = useState<TaxtypeValidation | null>(null);
  const [remaps, setRemaps] = useState<TaxtypeRemapEntry[] | null>(null);
  const [rowFixes, setRowFixes] = useState<TaxtypeRowFixEntry[] | null>(null);

  const [newRemapSource, setNewRemapSource] = useState("");
  const [newRemapTarget, setNewRemapTarget] = useState("");
  const [newFixIdParty, setNewFixIdParty] = useState("");
  const [newFixMigration, setNewFixMigration] = useState("VAT");
  const [newFixSource, setNewFixSource] = useState("");
  const [newFixTarget, setNewFixTarget] = useState("");

  async function withBusy(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function loadVatMapping() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setVatMapping(await getVatMapping(token, projectId));
    });
  }

  async function handleSaveVatMapping() {
    if (!vatMapping) return;
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { saved } = await saveVatMapping(token, projectId, vatMapping);
      setMessage(`Saved ${saved} mapping row(s).`);
    });
  }

  async function handleResetVatMapping() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { row_count } = await resetVatMapping(token, projectId);
      setMessage(`Reset to official defaults (${row_count} rows).`);
      setVatMapping(await getVatMapping(token, projectId));
    });
  }

  async function handleRunVatMigration() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await runVatMigration(token, projectId);
      setMigrationResult(result);
      setValidation(result.validation);
      setMessage(`VAT migration: ${result.migrated} row(s) written.`);
    });
  }

  async function handleRunSteuerMigration() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await runSteuerMigration(token, projectId);
      setMigrationResult(result);
      setValidation(result.validation);
      setMessage(`Steuernummer migration: ${result.migrated} row(s) written.`);
    });
  }

  async function loadValidation() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setValidation(await getTaxtypeValidation(token, projectId));
    });
  }

  async function loadRemaps() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setRemaps(await getTaxtypeRemaps(token, projectId));
    });
  }

  async function handleAddRemap() {
    if (!newRemapSource.trim() || !newRemapTarget.trim()) return;
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await saveTaxtypeRemap(token, projectId, newRemapSource, newRemapTarget);
      setNewRemapSource("");
      setNewRemapTarget("");
      setRemaps(await getTaxtypeRemaps(token, projectId));
      setMessage("Remap saved - takes effect on the next migration run.");
    });
  }

  async function handleDeleteRemap(sourceCode: string) {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await deleteTaxtypeRemaps(token, projectId, [sourceCode]);
      setRemaps(await getTaxtypeRemaps(token, projectId));
    });
  }

  async function loadRowFixes() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setRowFixes(await getTaxtypeRowFixes(token, projectId));
    });
  }

  async function handleAddRowFix() {
    if (!newFixIdParty.trim() || !newFixSource.trim() || !newFixTarget.trim()) return;
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await saveTaxtypeRowFix(token, projectId, {
        id_party: newFixIdParty,
        migration: newFixMigration,
        source_code: newFixSource,
        target_code: newFixTarget,
      });
      setNewFixIdParty("");
      setNewFixSource("");
      setNewFixTarget("");
      setRowFixes(await getTaxtypeRowFixes(token, projectId));
      setMessage("Row fix saved - takes effect on the next migration run.");
    });
  }

  async function handleDeleteRowFix(entry: TaxtypeRowFixEntry) {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await deleteTaxtypeRowFixes(token, projectId, [[entry.id_party, entry.migration, entry.source_code]]);
      setRowFixes(await getTaxtypeRowFixes(token, projectId));
    });
  }

  async function handleSuggest(row: TaxtypeValidationFinding) {
    const token = await getToken();
    if (!token) return;
    const suggested = await getCollisionSuggestion(
      token,
      projectId,
      (row.country_code || "").slice(0, 2),
      row.taxtype,
      row.migration,
    );
    if (suggested) setNewFixTarget(suggested);
    setNewFixIdParty(row.id_party);
    setNewFixMigration(row.migration);
    setNewFixSource(row.taxtype);
  }

  return (
    <div>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <h3>Run migration</h3>
      <p style={{ color: "#666" }}>
        Excludes each track&apos;s own junk population, applies country/entity TAXTYPE assignment
        (VAT: country -&gt; code mapping below, Russia always splits into RU1/RU3, Canada is
        pattern-assigned; Steuernummer: this project&apos;s FiscalRule SAP codes), then writes the
        result and re-validates TAXTYPE codes against the official SAP category list.
      </p>
      <div style={{ display: "flex", gap: "1rem" }}>
        <button onClick={handleRunVatMigration} disabled={busy}>
          🚀 Run VAT Migration
        </button>
        <button onClick={handleRunSteuerMigration} disabled={busy}>
          🚀 Run Steuernummer Migration
        </button>
      </div>
      {migrationResult && (
        <p style={{ marginTop: "0.5rem", color: "#666", fontSize: "0.85rem" }}>
          {migrationResult.total_raw} total · {migrationResult.total_junk_removed} junk excluded ·{" "}
          {migrationResult.total_empty_removed} empty excluded · {migrationResult.migrated} migrated
        </p>
      )}

      <hr style={{ margin: "2rem 0" }} />

      <h3>TAXTYPE validation</h3>
      <button onClick={loadValidation} disabled={busy}>
        🔄 Refresh validation
      </button>
      {validation && (
        <>
          {validation.error ? (
            <p style={{ color: "#888" }}>{validation.error}</p>
          ) : (
            <>
              <p style={{ marginTop: "0.5rem" }}>
                {validation.total} row(s) · unknown: {validation.unknown} · obsolete:{" "}
                {validation.obsolete} · country mismatch: {validation.mismatch} · VAT-category hint:{" "}
                {validation.vat_hint} · key collisions: {validation.collision}
              </p>
              {validation.findings && validation.findings.length > 0 && (
                <table style={{ borderCollapse: "collapse", fontSize: "0.8rem", width: "100%" }}>
                  <thead>
                    <tr>
                      {["Migration", "IDParty", "TAXTYPE", "Country", "Finding", "SAP Description", ""].map((h) => (
                        <th key={h} style={cell}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {validation.findings.slice(0, 100).map((f, i) => (
                      <tr key={i}>
                        <td style={cell}>{f.migration}</td>
                        <td style={cell}>{f.id_party}</td>
                        <td style={cell}>{f.taxtype}</td>
                        <td style={cell}>{f.country_code}</td>
                        <td style={cell}>{f.finding}</td>
                        <td style={cell}>{f.sap_description}</td>
                        <td style={cell}>
                          {f.finding === "KEY_COLLISION" && (
                            <button onClick={() => handleSuggest(f)} disabled={busy}>
                              Fix this row…
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </>
      )}

      <hr style={{ margin: "2rem 0" }} />

      <h3>TAXTYPE remap (global, by source code)</h3>
      <p style={{ color: "#666" }}>Re-applied to every future migration run.</p>
      <button onClick={loadRemaps} disabled={busy}>
        {remaps === null ? "Load remaps" : "Reload"}
      </button>
      {remaps !== null && (
        <>
          <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            <tbody>
              {remaps.map((r) => (
                <tr key={r.source_code}>
                  <td style={cell}>{r.source_code}</td>
                  <td style={cell}>→</td>
                  <td style={cell}>{r.target_code}</td>
                  <td style={cell}>
                    <button onClick={() => handleDeleteRemap(r.source_code)} disabled={busy}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
            <input
              placeholder="Source code"
              value={newRemapSource}
              onChange={(e) => setNewRemapSource(e.target.value)}
              style={{ width: "8rem" }}
            />
            <input
              placeholder="Target code"
              value={newRemapTarget}
              onChange={(e) => setNewRemapTarget(e.target.value)}
              style={{ width: "8rem" }}
            />
            <button onClick={handleAddRemap} disabled={busy}>
              Add
            </button>
          </div>
        </>
      )}

      <hr style={{ margin: "2rem 0" }} />

      <h3>TAXTYPE row fix (one specific record)</h3>
      <p style={{ color: "#666" }}>
        Resolves a collision for one IDParty + Migration + source code, without affecting other rows
        sharing that source code.
      </p>
      <button onClick={loadRowFixes} disabled={busy}>
        {rowFixes === null ? "Load row fixes" : "Reload"}
      </button>
      {rowFixes !== null && (
        <>
          <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            <tbody>
              {rowFixes.map((f) => (
                <tr key={`${f.id_party}-${f.migration}-${f.source_code}`}>
                  <td style={cell}>{f.id_party}</td>
                  <td style={cell}>{f.migration}</td>
                  <td style={cell}>{f.source_code}</td>
                  <td style={cell}>→</td>
                  <td style={cell}>{f.target_code}</td>
                  <td style={cell}>
                    <button onClick={() => handleDeleteRowFix(f)} disabled={busy}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
            <input
              placeholder="IDParty"
              value={newFixIdParty}
              onChange={(e) => setNewFixIdParty(e.target.value)}
              style={{ width: "8rem" }}
            />
            <select value={newFixMigration} onChange={(e) => setNewFixMigration(e.target.value)}>
              <option value="VAT">VAT</option>
              <option value="STEUERNUMMER">STEUERNUMMER</option>
            </select>
            <input
              placeholder="Source code"
              value={newFixSource}
              onChange={(e) => setNewFixSource(e.target.value)}
              style={{ width: "8rem" }}
            />
            <input
              placeholder="Target code"
              value={newFixTarget}
              onChange={(e) => setNewFixTarget(e.target.value)}
              style={{ width: "8rem" }}
            />
            <button onClick={handleAddRowFix} disabled={busy}>
              Add
            </button>
          </div>
        </>
      )}

      <hr style={{ margin: "2rem 0" }} />

      <h3>VAT country → TAXTYPE mapping</h3>
      <p style={{ color: "#666" }}>
        Russia and Canada are handled by special-case logic and ignore this table (Canada&apos;s rows
        here are documentary only).
      </p>
      {vatMapping === null ? (
        <button onClick={loadVatMapping} disabled={busy}>
          Load mapping
        </button>
      ) : (
        <>
          <div style={{ display: "flex", gap: "1rem", margin: "0.5rem 0" }}>
            <button onClick={handleSaveVatMapping} disabled={busy}>
              💾 Save changes
            </button>
            <button onClick={handleResetVatMapping} disabled={busy}>
              🔄 Reset to official defaults
            </button>
          </div>
          <div style={{ overflowY: "auto", maxHeight: 300, border: "1px solid #eee" }}>
            <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", width: "100%" }}>
              <thead>
                <tr>
                  {["Code", "Region"].map((h) => (
                    <th key={h} style={{ ...cell, position: "sticky", top: 0, background: "#f5f5f5" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {vatMapping.map((m, idx) => (
                  <tr key={m.code}>
                    <td style={cell}>{m.code}</td>
                    <td style={cell}>
                      <select
                        value={m.region}
                        onChange={(e) =>
                          setVatMapping((prev) =>
                            prev ? prev.map((r, i) => (i === idx ? { ...r, region: e.target.value } : r)) : prev,
                          )
                        }
                      >
                        <option value="EU / Europe">EU / Europe</option>
                        <option value="Non-EU">Non-EU</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function TaxCleansingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("fiscal");
  const [fiscalTab, setFiscalTab] = useState<FiscalSubTab>("analyse");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [vatResult, setVatResult] = useState<VatAnalysisResult | null>(null);
  const [dupResult, setDupResult] = useState<VatDuplicateRow[] | null>(null);
  const [fiscalResult, setFiscalResult] = useState<FiscalCodeAnalysisResult | null>(null);

  async function withBusy(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAnalyze() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await runVatAnalysis(token, projectId);
      setVatResult(result);
      setMessage(
        result.vies_backfilled > 0
          ? `Backfilled ${result.vies_backfilled} VATNumber(s) from ViesNumber. ${result.junk.length} issue(s) found.`
          : `${result.junk.length} issue(s) found.`,
      );
    });
  }

  async function handleDuplicates() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setDupResult(await runVatDuplicateCheck(token, projectId));
    });
  }

  async function handleFiscalAnalyze() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await runFiscalCodeAnalysis(token, projectId);
      setFiscalResult(result);
      setMessage(`${result.junk.length} issue(s) found.`);
    });
  }

  async function handleMarkDone() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "tax_cleansing", "done");
      router.push(`/dashboard/projects/${projectId}`);
    });
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 1100, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>💶 Tax Cleansing</h1>
      <p style={{ color: "#666" }}>
        Analysis and rule management for FiscalCode (Steuernummer) and VATNumber (USt-ID).
      </p>
      <p style={{ color: "#888", fontSize: "0.85rem" }}>
        Note: Excel export and SAP-Abgleich sync remain out of scope for Migration Preparation - see
        docs/ROADMAP.md.
      </p>

      <div style={{ display: "flex", gap: "0.5rem", margin: "1.5rem 0", borderBottom: "1px solid #ddd" }}>
        {(
          [
            ["fiscal", "🧾 Steuernummer-Cleansing"],
            ["vat", "💶 VAT-Cleansing"],
            ["migration", "🚀 Migration Preparation"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              padding: "0.5rem 1rem",
              border: "none",
              borderBottom: tab === key ? "2px solid #333" : "2px solid transparent",
              background: "transparent",
              fontWeight: tab === key ? 600 : 400,
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      {tab === "fiscal" && (
        <>
          <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
            <button
              onClick={() => setFiscalTab("analyse")}
              style={{ fontWeight: fiscalTab === "analyse" ? 600 : 400 }}
            >
              ⚖️ Analyse
            </button>
            <button
              onClick={() => setFiscalTab("regelwerk")}
              style={{ fontWeight: fiscalTab === "regelwerk" ? 600 : 400 }}
            >
              📋 Regelwerk
            </button>
          </div>

          {fiscalTab === "analyse" && (
            <>
              <h3>FiscalCode Analysis</h3>
              <p style={{ color: "#666" }}>
                2-stage process: syntax check (length 5-20, invalid characters), then pattern
                validation against this project&apos;s country/entity-type rules.
              </p>
              <button onClick={handleFiscalAnalyze} disabled={busy}>
                🚀 Start FiscalCode Analysis
              </button>
              {fiscalResult && (
                <>
                  <p style={{ marginTop: "1rem" }}>
                    {fiscalResult.junk.length === 0
                      ? "✅ All Fiscal Codes are valid - no syntax or pattern errors!"
                      : `❌ ${fiscalResult.junk.length} FiscalCode error(s) found.`}
                  </p>
                  {fiscalResult.junk.length > 0 && (
                    <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", width: "100%" }}>
                      <thead>
                        <tr>
                          {["IDParty", "CompanyName", "Country", "FiscalCode", "Reason", "Allowed Pattern"].map(
                            (h) => (
                              <th key={h} style={cell}>
                                {h}
                              </th>
                            ),
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {fiscalResult.junk.slice(0, 50).map((r, i) => (
                          <tr key={i}>
                            <td style={cell}>{r.id_party}</td>
                            <td style={cell}>{r.company_name}</td>
                            <td style={cell}>{r.country_code}</td>
                            <td style={cell}>{r.fiscal_code}</td>
                            <td style={cell}>{r.reason}</td>
                            <td style={cell}>{r.allowed_pattern}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <QualityReportTable rows={fiscalResult.quality_report} />
                </>
              )}
            </>
          )}

          {fiscalTab === "regelwerk" && (
            <>
              <h3>Länder-Validierungsregeln</h3>
              <p style={{ color: "#666" }}>
                Regex patterns used to validate FiscalCode per country and entity type. Changes save
                immediately to this project and take effect on the next analysis run.
              </p>
              <FiscalRulesEditor projectId={projectId} />
            </>
          )}
        </>
      )}

      {tab === "vat" && (
        <>
          <h3>Unified VAT Analysis</h3>
          <p style={{ color: "#666" }}>
            3-stage process: backfill empty VATNumber from ViesNumber, syntax check, then pattern
            validation against each country&apos;s VAT format.
          </p>
          <button onClick={handleAnalyze} disabled={busy}>
            🚀 Start Unified VAT Analysis
          </button>

          {vatResult && (
            <>
              {vatResult.ru_precleaning.length > 0 && (
                <div style={{ margin: "1rem 0" }}>
                  <h4>🇷🇺 RU pre-cleaning</h4>
                  <table style={{ borderCollapse: "collapse", fontSize: "0.85rem" }}>
                    <thead>
                      <tr>
                        {["IDParty", "Original", "INN", "KPP", "Reason"].map((h) => (
                          <th key={h} style={cell}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {vatResult.ru_precleaning.slice(0, 30).map((r, i) => (
                        <tr key={i}>
                          <td style={cell}>{r.id_party}</td>
                          <td style={cell}>{r.vat_number_original}</td>
                          <td style={cell}>{r.inn_cleaned}</td>
                          <td style={cell}>{r.kpp_cleaned}</td>
                          <td style={cell}>{r.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <p style={{ marginTop: "1rem" }}>
                {vatResult.junk.length === 0
                  ? "✅ All VAT numbers are valid - no syntax or pattern errors!"
                  : `❌ ${vatResult.junk.length} VAT error(s) found.`}
              </p>
              {vatResult.junk.length > 0 && (
                <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", width: "100%" }}>
                  <thead>
                    <tr>
                      {["IDParty", "CompanyName", "Country", "VATNumber", "Reason", "Rule"].map((h) => (
                        <th key={h} style={cell}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {vatResult.junk.slice(0, 50).map((r, i) => (
                      <tr key={i}>
                        <td style={cell}>{r.id_party}</td>
                        <td style={cell}>{r.company_name}</td>
                        <td style={cell}>{r.country_code}</td>
                        <td style={cell}>{r.vat_number}</td>
                        <td style={cell}>{r.reason}</td>
                        <td style={cell}>{r.rule_used}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <QualityReportTable rows={vatResult.quality_report} />
            </>
          )}

          <hr style={{ margin: "2.5rem 0" }} />

          <h3>VAT Duplicates</h3>
          <p style={{ color: "#666" }}>Mandanten sharing the same normalized VAT number.</p>
          <button onClick={handleDuplicates} disabled={busy}>
            🚀 Check for Duplicates
          </button>
          {dupResult && (
            <>
              <p style={{ marginTop: "1rem" }}>
                {dupResult.length === 0 ? "✅ No VAT duplicates found." : `❌ ${dupResult.length} duplicate row(s).`}
              </p>
              {dupResult.length > 0 && (
                <table style={{ borderCollapse: "collapse", fontSize: "0.85rem" }}>
                  <thead>
                    <tr>
                      {["IDParty", "CompanyName", "VATNumber"].map((h) => (
                        <th key={h} style={cell}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dupResult.map((r, i) => (
                      <tr key={i}>
                        <td style={cell}>{r.id_party}</td>
                        <td style={cell}>{r.company_name}</td>
                        <td style={cell}>{r.vat_number}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </>
      )}

      {tab === "migration" && <MigrationPreparationTab projectId={projectId} />}

      <hr style={{ margin: "2.5rem 0" }} />
      <button onClick={handleMarkDone} disabled={busy}>
        Mark this stage as done
      </button>
    </main>
  );
}
