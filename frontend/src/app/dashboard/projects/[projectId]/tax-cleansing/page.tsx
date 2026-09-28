"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Euro,
  Plus,
  RefreshCw,
  Rocket,
  Save,
  Trash2,
} from "lucide-react";
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
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Select,
  Table,
  Tabs,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@/components/ui";

type Tab = "fiscal" | "vat" | "migration";
type FiscalSubTab = "analyse" | "regelwerk";

function findingTone(finding: string): "neutral" | "brand" | "success" | "warning" | "danger" {
  const f = finding.toUpperCase();
  if (f.includes("COLLISION")) return "danger";
  if (f.includes("UNKNOWN") || f.includes("OBSOLETE") || f.includes("MISMATCH")) return "warning";
  if (f.includes("HINT")) return "brand";
  return "neutral";
}

function QualityReportTable({ rows }: { rows: QualityReportRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="mt-4">
      <Table>
        <Thead>
          <Tr>
            <Th>Typ</Th>
            <Th>Clients</Th>
            <Th>Valid</Th>
            <Th>Junk</Th>
            <Th>Empty</Th>
            <Th>% Valid</Th>
            <Th>% Junk</Th>
            <Th>% Empty</Th>
          </Tr>
        </Thead>
        <Tbody>
          {rows.map((r) => (
            <Tr key={r.type}>
              <Td className="font-medium text-ink-900">{r.type}</Td>
              <Td>{r.total_clients}</Td>
              <Td>{r.total_valid}</Td>
              <Td>{r.total_junk}</Td>
              <Td>{r.total_empty}</Td>
              <Td>{r.pct_valid}%</Td>
              <Td>{r.pct_junk}%</Td>
              <Td>{r.pct_empty}%</Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </div>
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
      <Button variant="secondary" onClick={load} disabled={busy}>
        {busy ? "Loading…" : "Load rules"}
      </Button>
    );
  }

  const filtered = rules
    .map((r, idx) => ({ r, idx }))
    .filter(({ r }) => !search || r.country_code.toUpperCase().includes(search.toUpperCase()));

  return (
    <div className="space-y-4">
      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Search country code…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-48"
        />
        <span className="text-sm text-ink-500">
          {filtered.length} of {rules.length} rules shown
        </span>
        <Button size="sm" onClick={handleSave} disabled={busy}>
          <Save className="h-3.5 w-3.5" />
          Save changes
        </Button>
        <Button size="sm" variant="secondary" onClick={handleReset} disabled={busy}>
          <RefreshCw className="h-3.5 w-3.5" />
          Reset to code defaults
        </Button>
      </div>
      <div className="max-h-[500px] overflow-auto rounded-lg border border-ink-200">
        <table className="w-full text-left text-sm">
          <Thead className="sticky top-0 z-10">
            <Tr>
              <Th>Land</Th>
              <Th>SAP Code</Th>
              <Th>Regex</Th>
              <Th>Aliases (JSON)</Th>
              <Th>Description</Th>
              <Th>Confidence</Th>
            </Tr>
          </Thead>
          <Tbody>
            {filtered.map(({ r, idx }) => (
              <Tr key={`${r.country_code}-${r.entity_type}`}>
                <Td className="whitespace-nowrap text-ink-900">
                  {r.country_code} / {r.entity_type}
                </Td>
                <Td className="whitespace-nowrap">{r.sap_code}</Td>
                <Td className="min-w-[10rem]">
                  <Input
                    value={r.regex}
                    onChange={(e) => updateRule(idx, { regex: e.target.value })}
                    className="text-xs"
                  />
                </Td>
                <Td className="min-w-[10rem]">
                  <Input
                    value={JSON.stringify(r.aliases)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value);
                        if (Array.isArray(parsed)) updateRule(idx, { aliases: parsed });
                      } catch {
                        // ignore until valid JSON
                      }
                    }}
                    className="text-xs"
                  />
                </Td>
                <Td className="min-w-[12rem]">
                  <Input
                    value={r.description}
                    onChange={(e) => updateRule(idx, { description: e.target.value })}
                    className="text-xs"
                  />
                </Td>
                <Td className="min-w-[8rem]">
                  <Select
                    value={r.confidence}
                    onChange={(e) => updateRule(idx, { confidence: e.target.value })}
                    className="text-xs"
                  >
                    <option value="HIGH">HIGH</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="LOW">LOW</option>
                  </Select>
                </Td>
              </Tr>
            ))}
          </Tbody>
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
    <div className="space-y-6">
      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}

      <Card>
        <CardHeader>
          <CardTitle>Run migration</CardTitle>
          <CardDescription>
            Excludes each track&apos;s own junk population, applies country/entity TAXTYPE assignment
            (VAT: country -&gt; code mapping below, Russia always splits into RU1/RU3, Canada is
            pattern-assigned; Steuernummer: this project&apos;s FiscalRule SAP codes), then writes the
            result and re-validates TAXTYPE codes against the official SAP category list.
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-3">
          <div className="flex flex-wrap gap-3">
            <Button onClick={handleRunVatMigration} disabled={busy}>
              <Rocket className="h-4 w-4" />
              Run VAT Migration
            </Button>
            <Button onClick={handleRunSteuerMigration} disabled={busy}>
              <Rocket className="h-4 w-4" />
              Run Steuernummer Migration
            </Button>
          </div>
          {migrationResult && (
            <p className="text-sm text-ink-500">
              {migrationResult.total_raw} total · {migrationResult.total_junk_removed} junk excluded ·{" "}
              {migrationResult.total_empty_removed} empty excluded · {migrationResult.migrated} migrated
            </p>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>TAXTYPE validation</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <Button size="sm" variant="secondary" onClick={loadValidation} disabled={busy}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh validation
          </Button>
          {validation && (
            <>
              {validation.error ? (
                <p className="text-sm text-ink-500">{validation.error}</p>
              ) : (
                <>
                  <p className="text-sm text-ink-700">
                    {validation.total} row(s) · unknown: {validation.unknown} · obsolete:{" "}
                    {validation.obsolete} · country mismatch: {validation.mismatch} · VAT-category hint:{" "}
                    {validation.vat_hint} · key collisions: {validation.collision}
                  </p>
                  {validation.findings && validation.findings.length > 0 && (
                    <Table>
                      <Thead>
                        <Tr>
                          <Th>Migration</Th>
                          <Th>IDParty</Th>
                          <Th>TAXTYPE</Th>
                          <Th>Country</Th>
                          <Th>Finding</Th>
                          <Th>SAP Description</Th>
                          <Th></Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {validation.findings.slice(0, 100).map((f, i) => (
                          <Tr key={i}>
                            <Td>{f.migration}</Td>
                            <Td>{f.id_party}</Td>
                            <Td>{f.taxtype}</Td>
                            <Td>{f.country_code}</Td>
                            <Td>
                              <Badge tone={findingTone(f.finding)}>{f.finding}</Badge>
                            </Td>
                            <Td>{f.sap_description}</Td>
                            <Td>
                              {f.finding === "KEY_COLLISION" && (
                                <Button size="sm" variant="secondary" onClick={() => handleSuggest(f)} disabled={busy}>
                                  Fix this row…
                                </Button>
                              )}
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  )}
                </>
              )}
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>TAXTYPE remap (global, by source code)</CardTitle>
          <CardDescription>Re-applied to every future migration run.</CardDescription>
        </CardHeader>
        <CardBody className="space-y-4">
          <Button size="sm" variant="secondary" onClick={loadRemaps} disabled={busy}>
            {remaps === null ? "Load remaps" : "Reload"}
          </Button>
          {remaps !== null && (
            <>
              {remaps.length > 0 && (
                <Table>
                  <Tbody>
                    {remaps.map((r) => (
                      <Tr key={r.source_code}>
                        <Td>{r.source_code}</Td>
                        <Td>
                          <ArrowRight className="h-3.5 w-3.5 text-ink-400" />
                        </Td>
                        <Td>{r.target_code}</Td>
                        <Td>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-red-600 hover:bg-red-50 hover:text-red-700"
                            onClick={() => handleDeleteRemap(r.source_code)}
                            disabled={busy}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            Delete
                          </Button>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  placeholder="Source code"
                  value={newRemapSource}
                  onChange={(e) => setNewRemapSource(e.target.value)}
                  className="w-32"
                />
                <Input
                  placeholder="Target code"
                  value={newRemapTarget}
                  onChange={(e) => setNewRemapTarget(e.target.value)}
                  className="w-32"
                />
                <Button size="sm" onClick={handleAddRemap} disabled={busy}>
                  <Plus className="h-3.5 w-3.5" />
                  Add
                </Button>
              </div>
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>TAXTYPE row fix (one specific record)</CardTitle>
          <CardDescription>
            Resolves a collision for one IDParty + Migration + source code, without affecting other rows
            sharing that source code.
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-4">
          <Button size="sm" variant="secondary" onClick={loadRowFixes} disabled={busy}>
            {rowFixes === null ? "Load row fixes" : "Reload"}
          </Button>
          {rowFixes !== null && (
            <>
              {rowFixes.length > 0 && (
                <Table>
                  <Tbody>
                    {rowFixes.map((f) => (
                      <Tr key={`${f.id_party}-${f.migration}-${f.source_code}`}>
                        <Td>{f.id_party}</Td>
                        <Td>{f.migration}</Td>
                        <Td>{f.source_code}</Td>
                        <Td>
                          <ArrowRight className="h-3.5 w-3.5 text-ink-400" />
                        </Td>
                        <Td>{f.target_code}</Td>
                        <Td>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-red-600 hover:bg-red-50 hover:text-red-700"
                            onClick={() => handleDeleteRowFix(f)}
                            disabled={busy}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            Delete
                          </Button>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  placeholder="IDParty"
                  value={newFixIdParty}
                  onChange={(e) => setNewFixIdParty(e.target.value)}
                  className="w-32"
                />
                <Select
                  value={newFixMigration}
                  onChange={(e) => setNewFixMigration(e.target.value)}
                  className="w-44"
                >
                  <option value="VAT">VAT</option>
                  <option value="STEUERNUMMER">STEUERNUMMER</option>
                </Select>
                <Input
                  placeholder="Source code"
                  value={newFixSource}
                  onChange={(e) => setNewFixSource(e.target.value)}
                  className="w-32"
                />
                <Input
                  placeholder="Target code"
                  value={newFixTarget}
                  onChange={(e) => setNewFixTarget(e.target.value)}
                  className="w-32"
                />
                <Button size="sm" onClick={handleAddRowFix} disabled={busy}>
                  <Plus className="h-3.5 w-3.5" />
                  Add
                </Button>
              </div>
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>VAT country → TAXTYPE mapping</CardTitle>
          <CardDescription>
            Russia and Canada are handled by special-case logic and ignore this table (Canada&apos;s rows
            here are documentary only).
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-4">
          {vatMapping === null ? (
            <Button variant="secondary" onClick={loadVatMapping} disabled={busy}>
              Load mapping
            </Button>
          ) : (
            <>
              <div className="flex flex-wrap gap-3">
                <Button size="sm" onClick={handleSaveVatMapping} disabled={busy}>
                  <Save className="h-3.5 w-3.5" />
                  Save changes
                </Button>
                <Button size="sm" variant="secondary" onClick={handleResetVatMapping} disabled={busy}>
                  <RefreshCw className="h-3.5 w-3.5" />
                  Reset to official defaults
                </Button>
              </div>
              <div className="max-h-[300px] overflow-auto rounded-lg border border-ink-200">
                <table className="w-full text-left text-sm">
                  <Thead className="sticky top-0 z-10">
                    <Tr>
                      <Th>Code</Th>
                      <Th>Region</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {vatMapping.map((m, idx) => (
                      <Tr key={m.code}>
                        <Td>{m.code}</Td>
                        <Td className="min-w-[10rem]">
                          <Select
                            value={m.region}
                            onChange={(e) =>
                              setVatMapping((prev) =>
                                prev ? prev.map((r, i) => (i === idx ? { ...r, region: e.target.value } : r)) : prev,
                              )
                            }
                            className="text-xs"
                          >
                            <option value="EU / Europe">EU / Europe</option>
                            <option value="Non-EU">Non-EU</option>
                          </Select>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </table>
              </div>
            </>
          )}
        </CardBody>
      </Card>
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
    <div className="space-y-6">
      <Link
        href={`/dashboard/projects/${projectId}`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to project
      </Link>

      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-ink-900">
          <Euro className="h-6 w-6 text-brand-600" />
          Tax Cleansing
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Analysis and rule management for FiscalCode (Steuernummer) and VATNumber (USt-ID).
        </p>
        <p className="mt-1 text-xs text-ink-400">
          Note: Excel export and SAP-Abgleich sync remain out of scope for Migration Preparation - see
          docs/ROADMAP.md.
        </p>
      </div>

      <Tabs
        items={[
          { key: "fiscal", label: "Steuernummer-Cleansing" },
          { key: "vat", label: "VAT-Cleansing" },
          { key: "migration", label: "Migration Preparation" },
        ]}
        active={tab}
        onChange={(key) => setTab(key as Tab)}
      />

      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}

      {tab === "fiscal" && (
        <div className="space-y-6">
          <Tabs
            items={[
              { key: "analyse", label: "Analyse" },
              { key: "regelwerk", label: "Regelwerk" },
            ]}
            active={fiscalTab}
            onChange={(key) => setFiscalTab(key as FiscalSubTab)}
          />

          {fiscalTab === "analyse" && (
            <Card>
              <CardHeader>
                <CardTitle>FiscalCode Analysis</CardTitle>
                <CardDescription>
                  2-stage process: syntax check (length 5-20, invalid characters), then pattern
                  validation against this project&apos;s country/entity-type rules.
                </CardDescription>
              </CardHeader>
              <CardBody className="space-y-4">
                <Button onClick={handleFiscalAnalyze} disabled={busy}>
                  <Rocket className="h-4 w-4" />
                  Start FiscalCode Analysis
                </Button>
                {fiscalResult && (
                  <>
                    {fiscalResult.junk.length === 0 ? (
                      <Alert tone="success">All Fiscal Codes are valid - no syntax or pattern errors!</Alert>
                    ) : (
                      <Alert tone="danger">{fiscalResult.junk.length} FiscalCode error(s) found.</Alert>
                    )}
                    {fiscalResult.junk.length > 0 && (
                      <Table>
                        <Thead>
                          <Tr>
                            <Th>IDParty</Th>
                            <Th>CompanyName</Th>
                            <Th>Country</Th>
                            <Th>FiscalCode</Th>
                            <Th>Reason</Th>
                            <Th>Allowed Pattern</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {fiscalResult.junk.slice(0, 50).map((r, i) => (
                            <Tr key={i}>
                              <Td>{r.id_party}</Td>
                              <Td>{r.company_name}</Td>
                              <Td>{r.country_code}</Td>
                              <Td>{r.fiscal_code}</Td>
                              <Td>{r.reason}</Td>
                              <Td>{r.allowed_pattern}</Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    )}
                    <QualityReportTable rows={fiscalResult.quality_report} />
                  </>
                )}
              </CardBody>
            </Card>
          )}

          {fiscalTab === "regelwerk" && (
            <Card>
              <CardHeader>
                <CardTitle>Länder-Validierungsregeln</CardTitle>
                <CardDescription>
                  Regex patterns used to validate FiscalCode per country and entity type. Changes save
                  immediately to this project and take effect on the next analysis run.
                </CardDescription>
              </CardHeader>
              <CardBody>
                <FiscalRulesEditor projectId={projectId} />
              </CardBody>
            </Card>
          )}
        </div>
      )}

      {tab === "vat" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Unified VAT Analysis</CardTitle>
              <CardDescription>
                3-stage process: backfill empty VATNumber from ViesNumber, syntax check, then pattern
                validation against each country&apos;s VAT format.
              </CardDescription>
            </CardHeader>
            <CardBody className="space-y-4">
              <Button onClick={handleAnalyze} disabled={busy}>
                <Rocket className="h-4 w-4" />
                Start Unified VAT Analysis
              </Button>

              {vatResult && (
                <>
                  {vatResult.ru_precleaning.length > 0 && (
                    <div>
                      <h4 className="mb-2 text-sm font-semibold text-ink-900">RU pre-cleaning</h4>
                      <Table>
                        <Thead>
                          <Tr>
                            <Th>IDParty</Th>
                            <Th>Original</Th>
                            <Th>INN</Th>
                            <Th>KPP</Th>
                            <Th>Reason</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {vatResult.ru_precleaning.slice(0, 30).map((r, i) => (
                            <Tr key={i}>
                              <Td>{r.id_party}</Td>
                              <Td>{r.vat_number_original}</Td>
                              <Td>{r.inn_cleaned}</Td>
                              <Td>{r.kpp_cleaned}</Td>
                              <Td>{r.reason}</Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </div>
                  )}

                  {vatResult.junk.length === 0 ? (
                    <Alert tone="success">All VAT numbers are valid - no syntax or pattern errors!</Alert>
                  ) : (
                    <Alert tone="danger">{vatResult.junk.length} VAT error(s) found.</Alert>
                  )}
                  {vatResult.junk.length > 0 && (
                    <Table>
                      <Thead>
                        <Tr>
                          <Th>IDParty</Th>
                          <Th>CompanyName</Th>
                          <Th>Country</Th>
                          <Th>VATNumber</Th>
                          <Th>Reason</Th>
                          <Th>Rule</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {vatResult.junk.slice(0, 50).map((r, i) => (
                          <Tr key={i}>
                            <Td>{r.id_party}</Td>
                            <Td>{r.company_name}</Td>
                            <Td>{r.country_code}</Td>
                            <Td>{r.vat_number}</Td>
                            <Td>{r.reason}</Td>
                            <Td>{r.rule_used}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  )}
                  <QualityReportTable rows={vatResult.quality_report} />
                </>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>VAT Duplicates</CardTitle>
              <CardDescription>Mandanten sharing the same normalized VAT number.</CardDescription>
            </CardHeader>
            <CardBody className="space-y-4">
              <Button onClick={handleDuplicates} disabled={busy}>
                <Rocket className="h-4 w-4" />
                Check for Duplicates
              </Button>
              {dupResult && (
                <>
                  {dupResult.length === 0 ? (
                    <Alert tone="success">No VAT duplicates found.</Alert>
                  ) : (
                    <Alert tone="danger">{dupResult.length} duplicate row(s).</Alert>
                  )}
                  {dupResult.length > 0 && (
                    <Table>
                      <Thead>
                        <Tr>
                          <Th>IDParty</Th>
                          <Th>CompanyName</Th>
                          <Th>VATNumber</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {dupResult.map((r, i) => (
                          <Tr key={i}>
                            <Td>{r.id_party}</Td>
                            <Td>{r.company_name}</Td>
                            <Td>{r.vat_number}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  )}
                </>
              )}
            </CardBody>
          </Card>
        </div>
      )}

      {tab === "migration" && <MigrationPreparationTab projectId={projectId} />}

      <div className="flex justify-end border-t border-ink-200 pt-6">
        <Button onClick={handleMarkDone} disabled={busy}>
          Mark this stage as done
        </Button>
      </div>
    </div>
  );
}
