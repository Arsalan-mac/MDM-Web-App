"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  downloadSapTemplateWorkbook,
  generateAllSapTemplateSheets,
  listSapTemplateSheets,
  previewSapTemplateSheet,
  setStageStatus,
  type SapTemplateGenerateAll,
  type SapTemplateSheetInfo,
  type SapTemplateSheetPreview,
} from "@/lib/api";

const cell: React.CSSProperties = { border: "1px solid #ccc", padding: "3px 8px", fontSize: "0.8rem" };

export default function SapTemplatePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [sheets, setSheets] = useState<SapTemplateSheetInfo[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>("");
  const [preview, setPreview] = useState<SapTemplateSheetPreview | null>(null);
  const [summary, setSummary] = useState<SapTemplateGenerateAll | null>(null);
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;
      try {
        const s = await listSapTemplateSheets(token, projectId);
        setSheets(s);
        if (s.length > 0) setSelectedSheet(s[0].name);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load sheets.");
      }
    })();
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

  async function handlePreview() {
    if (!selectedSheet) return;
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setPreview(await previewSapTemplateSheet(token, projectId, selectedSheet, 5));
    });
  }

  async function handleCheckAll() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setSummary(await generateAllSapTemplateSheets(token, projectId));
    });
  }

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const blob = await downloadSapTemplateWorkbook(token, projectId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "SAP_Migration_Template.xlsx";
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Workbook downloaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  }

  async function handleMarkDone() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "sap_template", "done");
      router.push(`/dashboard/projects/${projectId}`);
    });
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 1100, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>📦 SAP Template Migration</h1>
      <p style={{ color: "#666" }}>
        Generates SAP Business Partner master-data migration rows from Mandanten: BUT000-General
        (partner master data) and ADRC-Address. Ported as the first slice of this stage - the
        materialized-table sheets (BUT100/BUT0ID/BUT0IS/BUT000-Append), DFKKBPTAXNUM, country
        filtering, CSV export, and anonymization are deferred - see docs/ROADMAP.md.
      </p>

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <h3>Preview (5 rows)</h3>
      <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "1rem" }}>
        <select value={selectedSheet} onChange={(e) => setSelectedSheet(e.target.value)}>
          {sheets.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name} ({s.field_count} fields)
            </option>
          ))}
        </select>
        <button onClick={handlePreview} disabled={busy || !selectedSheet}>
          🔍 Preview
        </button>
      </div>

      {preview && (
        <>
          <p style={{ color: "#666" }}>
            {preview.total} total row(s) in this sheet · {preview.violations.length} violation(s) among the
            previewed rows
          </p>
          {preview.rows.length > 0 && (
            <div style={{ overflowX: "auto", marginBottom: "1rem" }}>
              <table style={{ borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    {Object.keys(preview.rows[0]).map((h) => (
                      <th key={h} style={cell}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, i) => (
                    <tr key={i}>
                      {Object.entries(row).map(([field, value]) => {
                        const violated = preview.violations.some((v) => v.row_index === i && v.field === field);
                        return (
                          <td key={field} style={{ ...cell, background: violated ? "#ffc7ce" : undefined }}>
                            {value}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {preview.violations.length > 0 && (
            <>
              <h4>Violations</h4>
              <table style={{ borderCollapse: "collapse", fontSize: "0.8rem" }}>
                <thead>
                  <tr>
                    {["IDParty", "Field", "Value", "Allowed length"].map((h) => (
                      <th key={h} style={cell}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.violations.map((v, i) => (
                    <tr key={i}>
                      <td style={cell}>{v.id_party}</td>
                      <td style={cell}>{v.field}</td>
                      <td style={cell}>{v.value}</td>
                      <td style={cell}>{v.allowed_length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}

      <hr style={{ margin: "2rem 0" }} />

      <h3>Generate</h3>
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
        <button onClick={handleCheckAll} disabled={busy}>
          📊 Check all sheets
        </button>
        <button onClick={handleDownload} disabled={downloading}>
          {downloading ? "Generating…" : "🚀 Generate & download workbook"}
        </button>
      </div>

      {summary && (
        <table style={{ borderCollapse: "collapse", fontSize: "0.85rem" }}>
          <thead>
            <tr>
              {["Sheet", "Rows", "Violations"].map((h) => (
                <th key={h} style={cell}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(summary.sheets).map(([name, s]) => (
              <tr key={name}>
                <td style={cell}>{name}</td>
                <td style={cell}>{s.total}</td>
                <td style={cell}>{s.violation_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <hr style={{ margin: "2.5rem 0" }} />
      <button onClick={handleMarkDone} disabled={busy}>
        Mark this stage as done
      </button>
    </main>
  );
}
