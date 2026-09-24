"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  clearAllRows,
  clearRowsByIds,
  listDeleteRecordsTables,
  setStageStatus,
  type DeleteRecordsTableInfo,
} from "@/lib/api";

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
    <main style={{ padding: "3rem", maxWidth: 900, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>🗑️ Delete Records</h1>
      <p style={{ color: "#666" }}>
        Nullify specific column values either across all rows or only for rows matching an
        uploaded ID list. Rows are never physically removed - only the selected field values are
        cleared.
      </p>

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <h3>Step 1 — Select Table</h3>
      <select value={table} onChange={(e) => setTable(e.target.value)}>
        {tables.map((t) => (
          <option key={t.table} value={t.table}>
            {t.table}
          </option>
        ))}
      </select>

      <h3>Step 2 — Select Columns to Clear</h3>
      {current && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem 1.5rem", maxWidth: 700 }}>
          {current.clearable_columns.map((c) => (
            <label key={c} style={{ fontSize: "0.9rem" }}>
              <input type="checkbox" checked={columns.includes(c)} onChange={() => toggleColumn(c)} /> {c}
            </label>
          ))}
        </div>
      )}
      {columns.length === 0 && <p style={{ color: "#666" }}>Select at least one column to continue.</p>}

      {columns.length > 0 && (
        <>
          <h3>Step 3 — Choose Deletion Mode</h3>
          <div style={{ display: "flex", gap: "1.5rem", marginBottom: "1rem" }}>
            <label>
              <input
                type="radio"
                checked={mode === "all"}
                onChange={() => {
                  setMode("all");
                  setConfirmed(false);
                }}
              />{" "}
              🧹 Clear for ALL rows
            </label>
            <label>
              <input
                type="radio"
                checked={mode === "ids"}
                onChange={() => {
                  setMode("ids");
                  setConfirmed(false);
                }}
              />{" "}
              📋 Clear for specific rows (uploaded ID list)
            </label>
          </div>

          {mode === "all" && (
            <>
              <p style={{ background: "#fff3cd", padding: "0.75rem", borderRadius: 4 }}>
                ⚠️ This will set <b>{columns.join(", ")}</b> to NULL for <b>every row</b> in <b>{table}</b>.
              </p>
              <label style={{ display: "block", margin: "0.5rem 0" }}>
                <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> I
                understand this will clear the selected columns for all rows.
              </label>
              <button onClick={handleClearAll} disabled={!canExecuteAll || busy}>
                🗑️ Execute Clear (All Rows)
              </button>
            </>
          )}

          {mode === "ids" && current && (
            <>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxWidth: 500 }}>
                <label>
                  Upload ID list (.csv / .txt / .xlsx)
                  <br />
                  <input type="file" accept=".csv,.txt,.xlsx,.xls" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                </label>
                <label>
                  Column name in the uploaded file containing the IDs
                  <br />
                  <input
                    value={excelIdCol}
                    onChange={(e) => setExcelIdCol(e.target.value)}
                    placeholder="e.g. IDParty"
                    style={{ width: "12rem" }}
                  />
                </label>
                <label>
                  Matching column in {table}
                  <br />
                  <select value={dbIdCol} onChange={(e) => setDbIdCol(e.target.value)}>
                    {current.columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <p style={{ background: "#fff3cd", padding: "0.75rem", borderRadius: 4, marginTop: "1rem" }}>
                ⚠️ This will set <b>{columns.join(", ")}</b> to NULL for rows in <b>{table}</b> where{" "}
                <b>{dbIdCol}</b> matches an ID from the uploaded file.
              </p>
              <label style={{ display: "block", margin: "0.5rem 0" }}>
                <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> I
                understand this will clear the selected columns for the matched rows.
              </label>
              <button onClick={handleClearByIds} disabled={!canExecuteIds || busy}>
                🗑️ Execute Clear (ID List)
              </button>
            </>
          )}
        </>
      )}

      <hr style={{ margin: "2.5rem 0" }} />
      <button onClick={handleMarkDone} disabled={busy}>
        Mark this stage as done
      </button>
    </main>
  );
}
