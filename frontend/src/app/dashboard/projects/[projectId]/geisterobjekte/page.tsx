"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getConsistencyCheck,
  getGeisterobjekteStatus,
  quarantineGhosts,
  restoreGhosts,
  setStageStatus,
  type ConsistencyFinding,
  type GeisterobjekteStatus,
} from "@/lib/api";

export default function GeisterobjektePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [status, setStatusState] = useState<GeisterobjekteStatus | null>(null);
  const [findings, setFindings] = useState<ConsistencyFinding[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    const token = await getToken();
    if (!token) return;
    try {
      setStatusState(await getGeisterobjekteStatus(token, projectId));
      setFindings(await getConsistencyCheck(token, projectId));
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

  async function handleQuarantine() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { quarantined } = await quarantineGhosts(token, projectId);
      setMessage(
        quarantined > 0
          ? `Moved ${quarantined} ghost object(s) to quarantine.`
          : "No ghost objects found — nothing to do.",
      );
      await reload();
    });
  }

  async function handleRestore() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { restored, skipped } = await restoreGhosts(token, projectId);
      setMessage(
        `Restored ${restored} object(s) to Mandanten.` +
          (skipped > 0 ? ` ${skipped} skipped (already present in Mandanten).` : ""),
      );
      await reload();
    });
  }

  async function handleMarkDone() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "geisterobjekte", "done");
      router.push(`/dashboard/projects/${projectId}`);
    });
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 800, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>👻 Geisterobjekte</h1>
      <p>
        Identifies Mandanten with no connection to any Auftrag, connected party, or opponent
        relationship, and moves them to a separate table (reversible).
      </p>

      {status && (
        <div style={{ display: "flex", gap: "2rem", margin: "1.5rem 0" }}>
          <div>
            <div style={{ fontSize: "1.5rem", fontWeight: 600 }}>{status.mandant_count}</div>
            <div style={{ color: "#666" }}>Rows in Mandanten</div>
          </div>
          <div>
            <div style={{ fontSize: "1.5rem", fontWeight: 600 }}>{status.ghost_count}</div>
            <div style={{ color: "#666" }}>Quarantined ghost objects</div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: "1rem" }}>
        <button onClick={handleQuarantine} disabled={busy}>
          ▶ Run ghost detection &amp; quarantine
        </button>
        <button onClick={handleRestore} disabled={busy || !status?.ghost_count}>
          🔁 Restore all to Mandanten
        </button>
      </div>

      {message && <p style={{ color: "green" }}>{message}</p>}
      {error && <p style={{ color: "crimson" }}>{error}</p>}

      <h2 style={{ marginTop: "2.5rem" }}>🧪 Consistency check</h2>
      <p style={{ color: "#666" }}>
        Result tables that still reference a now-quarantined ghost — their analysis ran before
        the quarantine and should be re-run.
      </p>
      {findings.length === 0 ? (
        <p style={{ color: "green" }}>✅ No stale references found.</p>
      ) : (
        <ul>
          {findings.map((f) => (
            <li key={f.table}>
              <strong>{f.table}</strong>: {f.ghost_rows} row(s) reference a quarantined ghost —{" "}
              {f.hint}
            </li>
          ))}
        </ul>
      )}

      <hr style={{ margin: "2.5rem 0" }} />
      <button onClick={handleMarkDone} disabled={busy}>
        Mark this stage as done
      </button>
    </main>
  );
}
