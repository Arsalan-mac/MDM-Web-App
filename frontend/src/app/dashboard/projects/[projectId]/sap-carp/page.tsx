"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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
    <div style={{ margin: "1.5rem 0", padding: "1rem", border: "1px solid #ddd", borderRadius: 6 }}>
      <h3 style={{ marginTop: 0 }}>{label}</h3>
      <p style={{ color: "#666", fontSize: "0.9rem" }}>{description}</p>
      <form onSubmit={handleSubmit}>
        <input type="file" accept=".csv,.txt,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button type="submit" disabled={!file || busy} style={{ marginLeft: "1rem" }}>
          {busy ? "Uploading…" : "Upload"}
        </button>
      </form>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}
    </div>
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
    <main style={{ padding: "3rem", maxWidth: 900, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>✏️ SAP-CARP-Ueberschreibung</h1>
      <p style={{ color: "#666" }}>
        Overwrite Mandanten fields from an SAP export via a field mapping, distribute CompanyName
        into the SAP Name 1-4 export slots, and split natural-person names into first/last name.
      </p>

      <div style={{ display: "flex", gap: "0.5rem", margin: "1.5rem 0", borderBottom: "1px solid #ddd" }}>
        {(
          [
            ["upload", "📤 SAP Data Upload"],
            ["overwrite", "🔄 Mapping & Ueberschreibung"],
            ["name-split", "🔤 Name Splitting"],
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

      {tab === "upload" && (
        <>
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
        </>
      )}

      {tab === "overwrite" && overwrite && nameDist && (
        <>
          <h2>Step 1 — Overwrite Mandanten</h2>
          <p style={{ color: "#666" }}>
            Join: <code>mandanten.IDParty</code> = <code>SAP-Allgemeine Stammdaten.{overwrite.sap_key_col ?? "?"}</code>
          </p>
          <ul>
            <li>{overwrite.field_ok ? "✅" : "❌"} Field-Mapping — {overwrite.mapping_rows} field mapping(s)</li>
            <li>{overwrite.sap_ok ? "✅" : "❌"} SAP-Allgemeine Stammdaten uploaded</li>
            <li>
              {overwrite.match_count > 0 ? "✅" : "⚠️"} {overwrite.match_count} IDParty match(es)
            </li>
            {overwrite.already_flagged > 0 && <li>ℹ️ {overwrite.already_flagged} already SAP-overridden</li>}
          </ul>
          {overwrite.missing_sap.length > 0 && (
            <p style={{ color: "#b58900" }}>
              ⚠️ Field-Mapping references SAP column(s) not present in the upload:{" "}
              {overwrite.missing_sap.join(", ")}
            </p>
          )}
          {overwrite.col_map.length > 0 && (
            <details style={{ margin: "1rem 0" }}>
              <summary>Field mapping ({overwrite.col_map.length})</summary>
              <table style={{ borderCollapse: "collapse", marginTop: "0.5rem" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "2px 8px" }}>Mandanten</th>
                    <th style={{ textAlign: "left", padding: "2px 8px" }}>SAP</th>
                    <th style={{ textAlign: "left", padding: "2px 8px" }}>Condition</th>
                  </tr>
                </thead>
                <tbody>
                  {overwrite.col_map.map((m) => (
                    <tr key={m.mandant_column}>
                      <td style={{ padding: "2px 8px" }}>{m.mandant_column}</td>
                      <td style={{ padding: "2px 8px" }}>{m.sap_column}</td>
                      <td style={{ padding: "2px 8px" }}>
                        {m.condition ? `IsOrganisation = ${m.condition}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
          <label style={{ display: "block", margin: "1rem 0" }}>
            <input type="checkbox" checked={resetFlag} onChange={(e) => setResetFlag(e.target.checked)} />{" "}
            Reset SapOverridden for all Mandanten before running
          </label>
          <button onClick={handleOverwriteRun} disabled={busy || !overwriteReady}>
            ▶ Mandanten überschreiben
          </button>

          <hr style={{ margin: "2.5rem 0" }} />

          <h2>Step 2 — CompanyName → Name 1-4</h2>
          <p style={{ color: "#666" }}>
            For IsOrganisation=1 rows: wraps CompanyName word-by-word into SAP&apos;s Name 1-4 export
            slots.
          </p>
          <p>
            {nameDist.affected_rows} row(s) affected · {nameDist.already_split} already split
          </p>
          <label style={{ display: "block", margin: "0.5rem 0" }}>
            Max characters per name field:{" "}
            <input
              type="number"
              min={1}
              max={200}
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value) || 40)}
              style={{ width: "4rem" }}
            />
          </label>
          <button onClick={handleNameDistRun} disabled={busy || nameDist.affected_rows === 0}>
            ▶ CompanyName verteilen
          </button>
        </>
      )}

      {tab === "name-split" && nameSplitStatus && (
        <>
          <h2>Step 3 — Name Splitting</h2>
          <p style={{ color: "#666" }}>
            Rule-based first/last-name extraction from CompanyName for natural persons
            (IsOrganisation=0) without a SAP override. 3+-token names with no comma are resolved via
            Claude when configured, otherwise flagged &quot;unklar&quot;.
          </p>
          <p>{nameSplitStatus.candidate_count} candidate(s) found</p>

          {nameSplitStatus.cleanup_count > 0 && (
            <div style={{ margin: "1rem 0" }}>
              <p style={{ color: "#b58900" }}>
                ⚠️ {nameSplitStatus.cleanup_count} record(s) have FirstName+LastName filled but
                CompanyName not yet cleared.
              </p>
              <button onClick={handleClearCompanyName} disabled={busy}>
                🧹 Clear CompanyName ({nameSplitStatus.cleanup_count})
              </button>
            </div>
          )}

          <button onClick={handlePreview} disabled={busy || nameSplitStatus.candidate_count === 0}>
            ▶ Vorschau generieren ({nameSplitStatus.candidate_count})
          </button>

          {preview && (
            <>
              <table style={{ borderCollapse: "collapse", width: "100%", marginTop: "1rem", fontSize: "0.9rem" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "4px 8px" }}>Apply</th>
                    <th style={{ textAlign: "left", padding: "4px 8px" }}>CompanyName</th>
                    <th style={{ textAlign: "left", padding: "4px 8px" }}>First name</th>
                    <th style={{ textAlign: "left", padding: "4px 8px" }}>Last name</th>
                    <th style={{ textAlign: "left", padding: "4px 8px" }}>Method</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((r) => (
                    <tr key={r.id_party}>
                      <td style={{ padding: "4px 8px" }}>
                        <input
                          type="checkbox"
                          checked={applied.has(r.id_party)}
                          onChange={(e) => {
                            const next = new Set(applied);
                            if (e.target.checked) next.add(r.id_party);
                            else next.delete(r.id_party);
                            setApplied(next);
                          }}
                        />
                      </td>
                      <td style={{ padding: "4px 8px" }}>{r.company_name}</td>
                      <td style={{ padding: "4px 8px" }}>{r.first_name}</td>
                      <td style={{ padding: "4px 8px" }}>{r.last_name}</td>
                      <td style={{ padding: "4px 8px" }}>{r.method}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ margin: "0.5rem 0" }}>
                {applied.size} of {preview.length} selected
              </p>
              <button onClick={handleApply} disabled={busy || applied.size === 0}>
                ✅ Ausgewählte anwenden ({applied.size})
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
