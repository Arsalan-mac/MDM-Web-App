"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  acceptAddressFinding,
  acceptZerlegung,
  listAddressJunk,
  listZerlegung,
  runAddressAnalysis,
  runZerlegung,
  type AnalysisSummary,
  type DecompositionResult,
  type DecompositionSummary,
  type JunkAddressFinding,
} from "@/lib/api";

const CONFIDENCE_LABEL: Record<string, string> = {
  hoch: "🟢 Hoch",
  mittel: "🟡 Mittel",
  niedrig: "🔴 Niedrig",
  "": "— (manuell)",
};

const cell: React.CSSProperties = { border: "1px solid #ccc", padding: "4px 8px" };

type Tab = "analyse" | "zerlegung";

function AdressAnalyseTab({ projectId }: { projectId: string }) {
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
    <>
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
                    <th key={h} style={cell}>
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.id}>
                  <td style={cell}>{f.IDParty}</td>
                  <td style={cell}>{f.CompanyName}</td>
                  <td style={cell}>{f.Address}</td>
                  <td style={cell}>{f.Reason}</td>
                  <td style={cell}>{f.Kategorie}</td>
                  <td style={cell}>{f.Aktion === "MANUELL" ? "—" : f.Aktion === "LEEREN" ? "(leeren)" : f.Neu}</td>
                  <td style={cell}>{CONFIDENCE_LABEL[f.Confidence]}</td>
                  <td style={cell}>
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
    </>
  );
}

function ZerlegungTab({ projectId }: { projectId: string }) {
  const { getToken } = useAuth();
  const [results, setResults] = useState<DecompositionResult[]>([]);
  const [summary, setSummary] = useState<DecompositionSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [useLlm, setUseLlm] = useState(true);
  const [spellOut, setSpellOut] = useState(false);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadResults() {
    const token = await getToken();
    if (!token) return;
    try {
      setResults(await listZerlegung(token, projectId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load results.");
    }
  }

  useEffect(() => {
    loadResults();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleRun() {
    setRunning(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setSummary(await runZerlegung(token, projectId, useLlm));
      await loadResults();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Zerlegung failed.");
    } finally {
      setRunning(false);
    }
  }

  async function handleAcceptConfidences(confidences: string[]) {
    setAccepting(confidences.join(","));
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { updated } = await acceptZerlegung(token, projectId, confidences, spellOut);
      setMessage(`Applied ${updated} record(s) to Mandanten.`);
      await loadResults();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Accept failed.");
    } finally {
      setAccepting(null);
    }
  }

  return (
    <>
      <p>
        Splits each client&apos;s free-text Address into SAP&apos;s ADRC target fields
        (STREET / HOUSE_NUM1 / STR_SUPPL1-3 / BUILDING) with a staged regex parser, falling
        back to a Claude Haiku batch call for addresses it can&apos;t confidently split.
        Junk addresses (from Adress-Analyse) aren&apos;t excluded - every partner belongs in
        the migration template, even with an incomplete address.
      </p>

      <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "0.5rem" }}>
        <label>
          <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} /> Use Claude Haiku
          for complex/uncertain cases
        </label>
        <button onClick={handleRun} disabled={running}>
          {running ? "Running…" : "Run Zerlegung"}
        </button>
      </div>

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      {summary && (
        <p style={{ color: "#444" }}>
          {summary.candidates} candidate(s) · {summary.sent_to_llm} sent to Claude ({summary.llm_resolved}{" "}
          resolved) · by confidence: {Object.entries(summary.by_confidence).map(([k, v]) => `${k || "manuell"}=${v}`).join(", ")}
        </p>
      )}

      <div style={{ display: "flex", gap: "1rem", alignItems: "center", margin: "1rem 0" }}>
        <label>
          <input type="checkbox" checked={spellOut} onChange={(e) => setSpellOut(e.target.checked)} /> Spell out
          &quot;Str.&quot; → &quot;Straße&quot;/&quot;Strasse&quot; where available
        </label>
        <button onClick={() => handleAcceptConfidences(["hoch"])} disabled={accepting !== null}>
          {accepting === "hoch" ? "…" : "Accept all Hoch"}
        </button>
        <button onClick={() => handleAcceptConfidences(["hoch", "mittel"])} disabled={accepting !== null}>
          {accepting === "hoch,mittel" ? "…" : "Accept Hoch + Mittel"}
        </button>
      </div>

      <h2>Proposals ({results.length})</h2>
      {results.length === 0 && <p>No open proposals - run Zerlegung above.</p>}
      {results.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.8rem" }}>
            <thead>
              <tr>
                {["IDParty", "Address", "STREET", "HOUSE_NUM1", "STR_SUPPL1", "BUILDING", "Method", "Confidence", "Hinweis"].map(
                  (h) => (
                    <th key={h} style={cell}>
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {results.slice(0, 200).map((r) => (
                <tr key={r.id}>
                  <td style={cell}>{r.IDParty}</td>
                  <td style={cell}>{r.Address}</td>
                  <td style={cell}>{r.STREET}</td>
                  <td style={cell}>{r.HOUSE_NUM1}</td>
                  <td style={cell}>{r.STR_SUPPL1}</td>
                  <td style={cell}>{r.BUILDING}</td>
                  <td style={cell}>{r.ParseMethod}</td>
                  <td style={cell}>{CONFIDENCE_LABEL[r.Confidence]}</td>
                  <td style={cell}>{r.Hinweis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export default function AddressCleansingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [tab, setTab] = useState<Tab>("analyse");

  return (
    <main style={{ padding: "3rem", maxWidth: 1100, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>Adress-Cleansing</h1>

      <div style={{ display: "flex", gap: "0.5rem", margin: "1.5rem 0", borderBottom: "1px solid #ddd" }}>
        {(
          [
            ["analyse", "⚖️ Adress-Analyse"],
            ["zerlegung", "🧩 Zerlegung"],
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

      {tab === "analyse" && <AdressAnalyseTab projectId={projectId} />}
      {tab === "zerlegung" && <ZerlegungTab projectId={projectId} />}
    </main>
  );
}
