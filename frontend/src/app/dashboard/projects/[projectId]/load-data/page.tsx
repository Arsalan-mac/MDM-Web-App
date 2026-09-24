"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { uploadMandanten, type LoadSummary } from "@/lib/api";

export default function LoadDataPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [summary, setSummary] = useState<LoadSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setSummary(await uploadMandanten(token, projectId, file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 800, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>Load Data — Mandanten (Initial Load)</h1>
      <p>
        Upload the client master-data file (.csv, .txt or .xlsx). This replaces the
        project&apos;s Mandanten table entirely — the same &quot;Initial Load&quot; behavior as
        the original tool. Delta upload isn&apos;t ported yet.
      </p>

      <form onSubmit={handleUpload} style={{ margin: "1.5rem 0" }}>
        <input
          type="file"
          accept=".csv,.txt,.xlsx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={!file || uploading} style={{ marginLeft: "1rem" }}>
          {uploading ? "Uploading…" : "Start Initial Load"}
        </button>
      </form>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {summary && (
        <>
          <p style={{ color: "green" }}>
            ✅ Loaded {summary.row_count} rows, {summary.columns.length} columns. The Load Data
            stage is now marked done.
          </p>
          <h3>Preview (first 5 rows)</h3>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.85rem" }}>
              <thead>
                <tr>
                  {summary.columns.map((col) => (
                    <th key={col} style={{ border: "1px solid #ccc", padding: "4px 8px", textAlign: "left" }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {summary.preview.map((row, i) => (
                  <tr key={i}>
                    {summary.columns.map((col) => (
                      <td key={col} style={{ border: "1px solid #ccc", padding: "4px 8px" }}>
                        {row[col] ?? ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
