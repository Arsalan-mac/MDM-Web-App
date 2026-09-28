"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, CheckCircle2, ListFilter, Trash2 } from "lucide-react";
import {
  clearAllRows,
  clearRowsByIds,
  listDeleteRecordsTables,
  setStageStatus,
  type DeleteRecordsTableInfo,
} from "@/lib/api";
import { Alert, Button, Card, CardBody, CardHeader, CardTitle, Input, Label, Select } from "@/components/ui";

type Mode = "all" | "ids";

export default function DeleteRecordsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [tables, setTables] = useState<DeleteRecordsTableInfo[]>([]);
  const [table, setTable] = useState("");
  const [columns, setColumns] = useState<string[]>([]);
  const [mode, setMode] = useState<Mode>("all");
  const [confirmed, setConfirmed] = useState(false);

  const [excelIdCol, setExcelIdCol] = useState("");
  const [dbIdCol, setDbIdCol] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;
      try {
        const t = await listDeleteRecordsTables(token, projectId);
        setTables(t);
        if (t.length > 0) setTable(t[0].table);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load tables.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const current = tables.find((t) => t.table === table);

  useEffect(() => {
    setColumns([]);
    setConfirmed(false);
    if (current) setDbIdCol(current.columns[0] ?? "");
  }, [table, current]);

  function toggleColumn(col: string) {
    setColumns((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]));
    setConfirmed(false);
  }

  async function handleClearAll() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { updated } = await clearAllRows(token, projectId, table, columns);
      setMessage(`Cleared ${columns.join(", ")} for ${updated} row(s) in ${table}.`);
      setConfirmed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Clear failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleClearByIds() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { updated } = await clearRowsByIds(token, projectId, table, columns, excelIdCol, dbIdCol, file);
      setMessage(`Cleared ${columns.join(", ")} for ${updated} matching row(s) in ${table}.`);
      setConfirmed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Clear failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleMarkDone() {
    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "delete", "done");
      router.push(`/dashboard/projects/${projectId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark done.");
    } finally {
      setBusy(false);
    }
  }

  const canExecuteAll = columns.length > 0 && confirmed;
  const canExecuteIds = columns.length > 0 && confirmed && file !== null && excelIdCol.trim() !== "" && dbIdCol !== "";

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
          <Trash2 className="h-6 w-6 text-brand-600" />
          Delete Records
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Nullify specific column values either across all rows or only for rows matching an
          uploaded ID list. Rows are never physically removed - only the selected field values are
          cleared.
        </p>
      </div>

      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}

      <Card>
        <CardHeader>
          <CardTitle>Step 1 — Select Table</CardTitle>
        </CardHeader>
        <CardBody>
          <Select value={table} onChange={(e) => setTable(e.target.value)} className="max-w-xs">
            {tables.map((t) => (
              <option key={t.table} value={t.table}>
                {t.table}
              </option>
            ))}
          </Select>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Step 2 — Select Columns to Clear</CardTitle>
        </CardHeader>
        <CardBody>
          {current && (
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {current.clearable_columns.map((c) => (
                <label key={c} className="flex items-center gap-2 text-sm text-ink-700">
                  <input
                    type="checkbox"
                    checked={columns.includes(c)}
                    onChange={() => toggleColumn(c)}
                    className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500/40"
                  />
                  {c}
                </label>
              ))}
            </div>
          )}
          {columns.length === 0 && <p className="mt-2 text-sm text-ink-500">Select at least one column to continue.</p>}
        </CardBody>
      </Card>

      {columns.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListFilter className="h-4 w-4 text-ink-400" />
              Step 3 — Choose Deletion Mode
            </CardTitle>
          </CardHeader>
          <CardBody className="space-y-4">
            <div className="flex flex-wrap gap-6">
              <label className="flex items-center gap-2 text-sm text-ink-700">
                <input
                  type="radio"
                  checked={mode === "all"}
                  onChange={() => {
                    setMode("all");
                    setConfirmed(false);
                  }}
                  className="h-4 w-4 border-ink-300 text-brand-600 focus:ring-brand-500/40"
                />
                Clear for ALL rows
              </label>
              <label className="flex items-center gap-2 text-sm text-ink-700">
                <input
                  type="radio"
                  checked={mode === "ids"}
                  onChange={() => {
                    setMode("ids");
                    setConfirmed(false);
                  }}
                  className="h-4 w-4 border-ink-300 text-brand-600 focus:ring-brand-500/40"
                />
                Clear for specific rows (uploaded ID list)
              </label>
            </div>

            {mode === "all" && (
              <div className="space-y-3">
                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <p>
                    This will set <b>{columns.join(", ")}</b> to NULL for <b>every row</b> in <b>{table}</b>.
                  </p>
                </div>
                <label className="flex items-center gap-2 text-sm text-ink-700">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                    className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500/40"
                  />
                  I understand this will clear the selected columns for all rows.
                </label>
                <Button variant="danger" onClick={handleClearAll} disabled={!canExecuteAll || busy}>
                  <Trash2 className="h-4 w-4" />
                  Execute Clear (All Rows)
                </Button>
              </div>
            )}

            {mode === "ids" && current && (
              <div className="space-y-4">
                <div className="flex max-w-md flex-col gap-4">
                  <div>
                    <Label>Upload ID list (.csv / .txt / .xlsx)</Label>
                    <input
                      type="file"
                      accept=".csv,.txt,.xlsx,.xls"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                      className="block w-full text-sm text-ink-600 file:mr-3 file:rounded-lg file:border-0 file:bg-ink-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-700 hover:file:bg-ink-200"
                    />
                  </div>
                  <div>
                    <Label>Column name in the uploaded file containing the IDs</Label>
                    <Input
                      value={excelIdCol}
                      onChange={(e) => setExcelIdCol(e.target.value)}
                      placeholder="e.g. IDParty"
                      className="max-w-[12rem]"
                    />
                  </div>
                  <div>
                    <Label>Matching column in {table}</Label>
                    <Select value={dbIdCol} onChange={(e) => setDbIdCol(e.target.value)} className="max-w-xs">
                      {current.columns.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>

                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <p>
                    This will set <b>{columns.join(", ")}</b> to NULL for rows in <b>{table}</b> where{" "}
                    <b>{dbIdCol}</b> matches an ID from the uploaded file.
                  </p>
                </div>
                <label className="flex items-center gap-2 text-sm text-ink-700">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                    className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500/40"
                  />
                  I understand this will clear the selected columns for the matched rows.
                </label>
                <Button variant="danger" onClick={handleClearByIds} disabled={!canExecuteIds || busy}>
                  <Trash2 className="h-4 w-4" />
                  Execute Clear (ID List)
                </Button>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      <div>
        <Button onClick={handleMarkDone} disabled={busy}>
          <CheckCircle2 className="h-4 w-4" />
          Mark this stage as done
        </Button>
      </div>
    </div>
  );
}
