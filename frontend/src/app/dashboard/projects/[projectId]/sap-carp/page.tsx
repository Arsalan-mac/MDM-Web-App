"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  Info,
  PlayCircle,
  Upload,
  XCircle,
} from "lucide-react";
import {
  applyNameSplit,
  clearRedundantCompanyNames,
  getNameDistributionStatus,
  getNameSplitStatus,
  getOverwriteStatus,
  previewNameSplit,
  runNameDistribution,
  runOverwrite,
  setStageStatus,
  uploadFieldMapping,
  uploadSapStammdaten,
  type NameDistributionStatus,
  type NameSplitPreviewRow,
  type NameSplitStatus,
  type OverwriteStatus,
} from "@/lib/api";
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Table,
  Tabs,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@/components/ui";

type Tab = "upload" | "overwrite" | "name-split";

function UploadForm({
  label,
  description,
  onUpload,
}: {
  label: string;
  description: string;
  onUpload: (file: File) => Promise<string>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setMessage(await onUpload(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{label}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardBody className="space-y-3">
        <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".csv,.txt,.xlsx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="flex-1 text-sm text-ink-600 file:mr-3 file:cursor-pointer file:rounded-md file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-brand-700 hover:file:bg-brand-100"
          />
          <Button type="submit" disabled={!file || busy}>
            <Upload className="h-4 w-4" />
            {busy ? "Uploading…" : "Upload"}
          </Button>
        </form>
        {error && <Alert tone="danger">{error}</Alert>}
        {message && <Alert tone="success">{message}</Alert>}
      </CardBody>
    </Card>
  );
}

export default function SapCarpPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("upload");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [overwrite, setOverwrite] = useState<OverwriteStatus | null>(null);
  const [resetFlag, setResetFlag] = useState(false);
  const [chunkSize, setChunkSize] = useState(40);
  const [nameDist, setNameDist] = useState<NameDistributionStatus | null>(null);
  const [nameSplitStatus, setNameSplitStatus] = useState<NameSplitStatus | null>(null);
  const [preview, setPreview] = useState<NameSplitPreviewRow[] | null>(null);
  const [applied, setApplied] = useState<Set<string>>(new Set());

  async function reload() {
    const token = await getToken();
    if (!token) return;
    try {
      setOverwrite(await getOverwriteStatus(token, projectId));
      setNameDist(await getNameDistributionStatus(token, projectId));
      setNameSplitStatus(await getNameSplitStatus(token, projectId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status.");
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

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

  async function handleOverwriteRun() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await runOverwrite(token, projectId, resetFlag);
      setMessage(`Overwrote ${result.flagged} Mandant(en), matched against ${result.sap_rows} SAP row(s).`);
      await reload();
    });
  }

  async function handleNameDistRun() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await runNameDistribution(token, projectId, chunkSize);
      setMessage(`Distributed CompanyName into Name 1-4 for ${result.affected} record(s).`);
      await reload();
    });
  }

  async function handlePreview() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const rows = await previewNameSplit(token, projectId);
      setPreview(rows);
      setApplied(new Set(rows.filter((r) => r.method !== "unklar").map((r) => r.id_party)));
    });
  }

  async function handleApply() {
    if (!preview) return;
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const entries = preview
        .filter((r) => applied.has(r.id_party))
        .map((r) => ({ id_party: r.id_party, first_name: r.first_name, last_name: r.last_name }));
      const result = await applyNameSplit(token, projectId, entries);
      setMessage(`Wrote FirstName/LastName for ${result.written} record(s).`);
      setPreview(null);
      await reload();
    });
  }

  async function handleClearCompanyName() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await clearRedundantCompanyNames(token, projectId);
      setMessage(`Cleared CompanyName for ${result.cleared} record(s).`);
      await reload();
    });
  }

  async function handleMarkDone() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "sap_carp", "done");
      router.push(`/dashboard/projects/${projectId}`);
    });
  }

  const overwriteReady =
    overwrite?.sap_ok && overwrite?.field_ok && overwrite?.mandant_ok && overwrite.match_count > 0;

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
        <h1 className="text-2xl font-semibold text-ink-900">SAP-CARP-Überschreibung</h1>
        <p className="mt-1 text-sm text-ink-500">
          Overwrite Mandanten fields from an SAP export via a field mapping, distribute CompanyName
          into the SAP Name 1-4 export slots, and split natural-person names into first/last name.
        </p>
      </div>

      <Tabs
        items={[
          { key: "upload", label: "SAP Data Upload" },
          { key: "overwrite", label: "Mapping & Überschreibung" },
          { key: "name-split", label: "Name Splitting" },
        ]}
        active={tab}
        onChange={(key) => setTab(key as Tab)}
      />

      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}

      {tab === "upload" && (
        <div className="space-y-6">
          <UploadForm
            label="SAP-Allgemeine Stammdaten"
            description="Join key: 'IDParty' on newer exports, 'Ext. Partnernummer' on older ones."
            onUpload={async (file) => {
              const token = await getToken();
              if (!token) throw new Error("Not signed in.");
              const r = await uploadSapStammdaten(token, projectId, file);
              await reload();
              return `Loaded ${r.row_count} row(s), key column '${r.sap_key_col}'${
                r.dup_keys > 0 ? `, ${r.dup_keys} duplicate key(s) skipped` : ""
              }.`;
            }}
          />
          <UploadForm
            label="Field-Mapping"
            description='Columns: "Mandanten", "SAP-Allgemeine Stammdaten", "Condition" (e.g. "IsOrganisation = 1").'
            onUpload={async (file) => {
              const token = await getToken();
              if (!token) throw new Error("Not signed in.");
              const r = await uploadFieldMapping(token, projectId, file);
              await reload();
              return `Loaded ${r.row_count} mapping row(s).`;
            }}
          />
        </div>
      )}

      {tab === "overwrite" && overwrite && nameDist && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Step 1 — Overwrite Mandanten</CardTitle>
              <CardDescription>
                Join: <code>mandanten.IDParty</code> ={" "}
                <code>SAP-Allgemeine Stammdaten.{overwrite.sap_key_col ?? "?"}</code>
              </CardDescription>
            </CardHeader>
            <CardBody className="space-y-4">
              <ul className="space-y-1.5 text-sm text-ink-700">
                <li className="flex items-center gap-2">
                  {overwrite.field_ok ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-red-600" />
                  )}
                  Field-Mapping — {overwrite.mapping_rows} field mapping(s)
                </li>
                <li className="flex items-center gap-2">
                  {overwrite.sap_ok ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-red-600" />
                  )}
                  SAP-Allgemeine Stammdaten uploaded
                </li>
                <li className="flex items-center gap-2">
                  {overwrite.match_count > 0 ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                  )}
                  {overwrite.match_count} IDParty match(es)
                </li>
                {overwrite.already_flagged > 0 && (
                  <li className="flex items-center gap-2 text-ink-600">
                    <Info className="h-4 w-4 shrink-0 text-brand-600" />
                    {overwrite.already_flagged} already SAP-overridden
                  </li>
                )}
              </ul>

              {overwrite.missing_sap.length > 0 && (
                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <div>
                    Field-Mapping references SAP column(s) not present in the upload:{" "}
                    {overwrite.missing_sap.join(", ")}
                  </div>
                </div>
              )}

              {overwrite.col_map.length > 0 && (
                <details className="rounded-lg border border-ink-200">
                  <summary className="cursor-pointer select-none px-3.5 py-2.5 text-sm font-medium text-ink-700">
                    Field mapping ({overwrite.col_map.length})
                  </summary>
                  <div className="border-t border-ink-200 p-3">
                    <Table>
                      <Thead>
                        <Tr>
                          <Th>Mandanten</Th>
                          <Th>SAP</Th>
                          <Th>Condition</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {overwrite.col_map.map((m) => (
                          <Tr key={m.mandant_column}>
                            <Td>{m.mandant_column}</Td>
                            <Td>{m.sap_column}</Td>
                            <Td>{m.condition ? `IsOrganisation = ${m.condition}` : "—"}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </div>
                </details>
              )}

              <label className="flex items-center gap-2 text-sm text-ink-700">
                <input
                  type="checkbox"
                  checked={resetFlag}
                  onChange={(e) => setResetFlag(e.target.checked)}
                  className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-2 focus:ring-brand-500/40"
                />
                Reset SapOverridden for all Mandanten before running
              </label>

              <Button onClick={handleOverwriteRun} disabled={busy || !overwriteReady}>
                <PlayCircle className="h-4 w-4" />
                Mandanten überschreiben
              </Button>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Step 2 — CompanyName → Name 1-4</CardTitle>
              <CardDescription>
                For IsOrganisation=1 rows: wraps CompanyName word-by-word into SAP&apos;s Name 1-4
                export slots.
              </CardDescription>
            </CardHeader>
            <CardBody className="space-y-4">
              <p className="text-sm text-ink-600">
                {nameDist.affected_rows} row(s) affected · {nameDist.already_split} already split
              </p>
              <div className="max-w-xs">
                <Label htmlFor="chunk-size">Max characters per name field</Label>
                <Input
                  id="chunk-size"
                  type="number"
                  min={1}
                  max={200}
                  value={chunkSize}
                  onChange={(e) => setChunkSize(Number(e.target.value) || 40)}
                  className="w-24"
                />
              </div>
              <Button onClick={handleNameDistRun} disabled={busy || nameDist.affected_rows === 0}>
                <PlayCircle className="h-4 w-4" />
                CompanyName verteilen
              </Button>
            </CardBody>
          </Card>
        </div>
      )}

      {tab === "name-split" && nameSplitStatus && (
        <Card>
          <CardHeader>
            <CardTitle>Step 3 — Name Splitting</CardTitle>
            <CardDescription>
              Rule-based first/last-name extraction from CompanyName for natural persons
              (IsOrganisation=0) without a SAP override. 3+-token names with no comma are resolved
              via Claude when configured, otherwise flagged &quot;unklar&quot;.
            </CardDescription>
          </CardHeader>
          <CardBody className="space-y-4">
            <p className="text-sm text-ink-600">{nameSplitStatus.candidate_count} candidate(s) found</p>

            {nameSplitStatus.cleanup_count > 0 && (
              <div className="space-y-2">
                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <div>
                    {nameSplitStatus.cleanup_count} record(s) have FirstName+LastName filled but
                    CompanyName not yet cleared.
                  </div>
                </div>
                <Button variant="secondary" onClick={handleClearCompanyName} disabled={busy}>
                  Clear CompanyName ({nameSplitStatus.cleanup_count})
                </Button>
              </div>
            )}

            <Button onClick={handlePreview} disabled={busy || nameSplitStatus.candidate_count === 0}>
              <PlayCircle className="h-4 w-4" />
              Vorschau generieren ({nameSplitStatus.candidate_count})
            </Button>

            {preview && (
              <div className="space-y-3">
                <Table>
                  <Thead>
                    <Tr>
                      <Th>Apply</Th>
                      <Th>CompanyName</Th>
                      <Th>First name</Th>
                      <Th>Last name</Th>
                      <Th>Method</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {preview.map((r) => (
                      <Tr key={r.id_party}>
                        <Td>
                          <input
                            type="checkbox"
                            checked={applied.has(r.id_party)}
                            onChange={(e) => {
                              const next = new Set(applied);
                              if (e.target.checked) next.add(r.id_party);
                              else next.delete(r.id_party);
                              setApplied(next);
                            }}
                            className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-2 focus:ring-brand-500/40"
                          />
                        </Td>
                        <Td>{r.company_name}</Td>
                        <Td>{r.first_name}</Td>
                        <Td>{r.last_name}</Td>
                        <Td>{r.method}</Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
                <div className="flex items-center justify-between">
                  <p className="text-sm text-ink-600">
                    {applied.size} of {preview.length} selected
                  </p>
                  <Button onClick={handleApply} disabled={busy || applied.size === 0}>
                    <CheckCircle2 className="h-4 w-4" />
                    Ausgewählte anwenden ({applied.size})
                  </Button>
                </div>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      <div className="flex justify-end border-t border-ink-200 pt-6">
        <Button variant="secondary" onClick={handleMarkDone} disabled={busy}>
          Mark this stage as done
        </Button>
      </div>
    </div>
  );
}
