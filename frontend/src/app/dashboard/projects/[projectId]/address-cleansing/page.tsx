"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  acceptAddressFinding,
  listAddressJunk,
  runAddressAnalysis,
  type AnalysisSummary,
  type JunkAddressFinding,
} from "@/lib/api";

const CONFIDENCE_LABEL: Record<string, string> = {
  hoch: "🟢 Hoch",
  mittel: "🟡 Mittel",
  niedrig: "🔴 Niedrig",
  "": "— (manuell)",
};

export default function AddressCleansingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const [findings, setFindings] = useState<JunkAddressFinding[]>([]);
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadFindings() {
    const token = await getToken();
    if (!token) return;
    try {
      setFindings(await listAddressJunk(token, projectId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load findings.");
    }
  }

  useEffect(() => {
    loadFindings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleAnalyze() {
    setAnalyzing(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setSummary(await runAddressAnalysis(token, projectId));
      await loadFindings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleAccept(findingId: string) {
    setAcceptingId(findingId);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await acceptAddressFinding(token, projectId, findingId);
      await loadFindings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Accept failed.");
    } finally {
      setAcceptingId(null);
    }
  }

  const canAccept = (f: JunkAddressFinding) =>
    (f.Aktion === "ERSETZEN" || f.Aktion === "LEEREN") && (f.Confidence === "hoch" || f.Confidence === "mittel");

  return (
    <main style={{ padding: "3rem", maxWidth: 1000, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>Adress-Cleansing — Adress-Analyse</h1>
      <p>
        Checks every client&apos;s Address field for placeholders, legal-form/contact-info
        text, missing house numbers, and city/postal-code text embedded in the address.
        PLZ and City checks aren&apos;t ported yet (they need the separate Referenzdaten
        stage) - see the project roadmap.
      </p>

      <button onClick={handleAnalyze} disabled={analyzing}>
        {analyzing ? "Analyzing…" : "Run Adress-Analyse"}
      </button>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {summary && (
        <p style={{ color: "green" }}>
          ✅ Checked {summary.rows_checked} records, {summary.findings} findings.
        </p>
      )}

      <h2>Findings ({findings.length})</h2>
      {findings.length === 0 && <p>No open findings.</p>}
      {findings.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.85rem" }}>
            <thead>
              <tr>
                {["IDParty", "Company", "Address", "Reason", "Category", "Proposal", "Confidence", ""].map(
                  (h) => (
                    <th key={h} style={{ border: "1px solid #ccc", padding: "4px 8px", textAlign: "left" }}>
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.id}>
                  <td style={{ border: "1px solid #ccc", padding: "4px 8px" }}>{f.IDParty}</td>
                  <td style={{ border: "1px solid #ccc", padding: "4px 8px" }}>{f.CompanyName}</td>
                  <td style={{ border: "1px solid #ccc", padding: "4px 8px" }}>{f.Address}</td>
                  <td style={{ border: "1px solid #ccc", padding: "4px 8px" }}>{f.Reason}</td>
                  <td style={{ border: "1px solid #ccc", padding: "4px 8px" }}>{f.Kategorie}</td>
                  <td style={{ border: "1px solid #ccc", padding: "4px 8px" }}>
                    {f.Aktion === "MANUELL" ? "—" : f.Aktion === "LEEREN" ? "(leeren)" : f.Neu}
                  </td>
                  <td style={{ border: "1px solid #ccc", padding: "4px 8px" }}>
                    {CONFIDENCE_LABEL[f.Confidence]}
                  </td>
                  <td style={{ border: "1px solid #ccc", padding: "4px 8px" }}>
                    {canAccept(f) ? (
                      <button onClick={() => handleAccept(f.id)} disabled={acceptingId === f.id}>
                        {acceptingId === f.id ? "…" : "Accept"}
                      </button>
                    ) : (
                      <span style={{ opacity: 0.5 }}>manual</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
