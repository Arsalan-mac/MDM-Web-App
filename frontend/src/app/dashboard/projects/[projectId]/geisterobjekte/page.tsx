"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, FlaskConical, Ghost, Play, RotateCcw } from "lucide-react";
import {
  getConsistencyCheck,
  getGeisterobjekteStatus,
  quarantineGhosts,
  restoreGhosts,
  setStageStatus,
  type ConsistencyFinding,
  type GeisterobjekteStatus,
} from "@/lib/api";
import { Alert, Button, Card, CardBody, EmptyState } from "@/components/ui";

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
    <div className="space-y-6">
      <Link
        href={`/dashboard/projects/${projectId}`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to project
      </Link>

      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
          <Ghost className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Geisterobjekte</h1>
          <p className="text-sm text-ink-500">
            Identifies Mandanten with no connection to any Auftrag, connected party, or opponent
            relationship, and moves them to a separate table (reversible).
          </p>
        </div>
      </div>

      <Card>
        <CardBody className="space-y-4">
          {status && (
            <div className="flex gap-8">
              <div>
                <div className="text-2xl font-semibold text-ink-900">{status.mandant_count}</div>
                <div className="text-sm text-ink-500">Rows in Mandanten</div>
              </div>
              <div>
                <div className="text-2xl font-semibold text-ink-900">{status.ghost_count}</div>
                <div className="text-sm text-ink-500">Quarantined ghost objects</div>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <Button onClick={handleQuarantine} disabled={busy}>
              <Play className="h-4 w-4" />
              Run ghost detection &amp; quarantine
            </Button>
            <Button variant="secondary" onClick={handleRestore} disabled={busy || !status?.ghost_count}>
              <RotateCcw className="h-4 w-4" />
              Restore all to Mandanten
            </Button>
          </div>

          {message && <Alert tone="success">{message}</Alert>}
          {error && <Alert tone="danger">{error}</Alert>}
        </CardBody>
      </Card>

      <Card>
        <CardBody className="space-y-3">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-ink-400" />
            <h2 className="text-sm font-semibold text-ink-900">Consistency check</h2>
          </div>
          <p className="text-sm text-ink-500">
            Result tables that still reference a now-quarantined ghost — their analysis ran
            before the quarantine and should be re-run.
          </p>
          {findings.length === 0 ? (
            <EmptyState title="No stale references found" />
          ) : (
            <ul className="space-y-1.5 text-sm">
              {findings.map((f) => (
                <li key={f.table} className="rounded-lg bg-ink-50 px-3 py-2">
                  <span className="font-semibold text-ink-900">{f.table}</span>
                  <span className="text-ink-600">
                    : {f.ghost_rows} row(s) reference a quarantined ghost — {f.hint}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Button onClick={handleMarkDone} disabled={busy}>
        Mark this stage as done
      </Button>
    </div>
  );
}
