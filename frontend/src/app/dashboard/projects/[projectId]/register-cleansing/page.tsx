"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  acceptRegisterCleansing,
  listRegisterCleansingProposals,
  runRegisterCleansing,
  setStageStatus,
  type RegisterCleansingProposal,
  type RegisterCleansingSummary,
} from "@/lib/api";

const cell: React.CSSProperties = { border: "1px solid #ccc", padding: "4px 8px", fontSize: "0.8rem" };

const CONFIDENCE_LABEL: Record<string, string> = {
  HIGH: "🟢 High",
  MEDIUM: "🟡 Medium",
  LOW: "🔴 Low",
};

export default function RegisterCleansingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [proposals, setProposals] = useState<RegisterCleansingProposal[]>([]);
  const [summary, setSummary] = useState<RegisterCleansingSummary | null>(null);
  const [useLlm, setUseLlm] = useState(true);
  const [running, setRunning] = useState(false);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadProposals() {
    const token = await getToken();
    if (!token) return;
    try {
      setProposals(await listRegisterCleansingProposals(token, projectId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load proposals.");
    }
  }

  useEffect(() => {
    loadProposals();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleRun() {
    setRunning(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setSummary(await runRegisterCleansing(token, projectId, useLlm));
      await loadProposals();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cleansing failed.");
    } finally {
      setRunning(false);
    }
  }

  async function handleAccept(confidences: string[]) {
    setAccepting(confidences.join(","));
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { updated } = await acceptRegisterCleansing(token, projectId, confidences);
      setMessage(`Applied ${updated} proposal(s) to Mandanten.`);
      await loadProposals();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Accept failed.");
    } finally {
      setAccepting(null);
    }
  }

  async function handleMarkDone() {
    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "register_clean", "done");
      router.push(`/dashboard/projects/${projectId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark done.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 1100, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>🏛 RegisterNumber Cleansing</h1>
      <p style={{ color: "#666" }}>
        Standardizes Mandant.RegisterNumber in two stages: deterministic prefix/whitespace
        normalization (&quot;HRB3792&quot; → &quot;HRB 3792&quot;), then a Claude Haiku pass for
        special forms (legacy &quot;HRN&quot; prefix, embedded court text) the deterministic
        pass can&apos;t handle. Junk values (checked by Quality Analysis&apos;s Register-Nr.
        check) are excluded - this stage never invents a number for a value that isn&apos;t one.
        Changes are proposals only; review and explicitly accept below.
      </p>

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginBottom: "1rem" }}>
        <label>
          <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} /> Use Claude Haiku
          for special forms
        </label>
        <button onClick={handleRun} disabled={running}>
          {running ? "Running…" : "🚀 Run Cleansing"}
        </button>
      </div>

      {summary && (
        <p style={{ color: "#444" }}>
          {summary.filled} filled value(s) · {summary.junk} junk (unchanged, see Quality) ·{" "}
          {summary.canonical} already canonical · {summary.std} standardized · {summary.llm_candidates}{" "}
          LLM candidate(s), {summary.llm_done} resolved
        </p>
      )}

      <div style={{ display: "flex", gap: "1rem", alignItems: "center", margin: "1rem 0" }}>
        <button onClick={() => handleAccept(["HIGH"])} disabled={accepting !== null}>
          {accepting === "HIGH" ? "…" : "Accept all High"}
        </button>
        <button onClick={() => handleAccept(["HIGH", "MEDIUM"])} disabled={accepting !== null}>
          {accepting === "HIGH,MEDIUM" ? "…" : "Accept High + Medium"}
        </button>
      </div>

      <h2>Proposals ({proposals.length})</h2>
      {proposals.length === 0 && <p>No open proposals - run Cleansing above.</p>}
      {proposals.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                {["IDParty", "Company", "Country", "Alt", "Neu", "Stufe", "Confidence", "Begruendung"].map((h) => (
                  <th key={h} style={cell}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {proposals.slice(0, 200).map((p) => (
                <tr key={p.id}>
                  <td style={cell}>{p.IDParty}</td>
                  <td style={cell}>{p.CompanyName}</td>
                  <td style={cell}>{p.CountryCode}</td>
                  <td style={cell}>{p.RegisterNumber_Alt}</td>
                  <td style={cell}>{p.RegisterNumber_Neu}</td>
                  <td style={cell}>{p.Stufe}</td>
                  <td style={cell}>{CONFIDENCE_LABEL[p.Confidence]}</td>
                  <td style={cell}>{p.Begruendung}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <hr style={{ margin: "2.5rem 0" }} />
      <button onClick={handleMarkDone} disabled={busy}>
        Mark this stage as done
      </button>
    </main>
  );
}
