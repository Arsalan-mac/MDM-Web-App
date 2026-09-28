"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Check, CheckCircle2, Landmark, PlayCircle } from "lucide-react";
import {
  acceptRegisterCleansing,
  listRegisterCleansingProposals,
  runRegisterCleansing,
  setStageStatus,
  type RegisterCleansingProposal,
  type RegisterCleansingSummary,
} from "@/lib/api";
import { Alert, Badge, Button, Card, CardBody, CardHeader, CardTitle, EmptyState, Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui";

const CONFIDENCE_LABEL: Record<string, string> = {
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
};

const CONFIDENCE_TONE: Record<string, "success" | "warning" | "danger"> = {
  HIGH: "success",
  MEDIUM: "warning",
  LOW: "danger",
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
          <Landmark className="h-6 w-6 text-brand-600" />
          RegisterNumber Cleansing
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Standardizes Mandant.RegisterNumber in two stages: deterministic prefix/whitespace
          normalization (&quot;HRB3792&quot; → &quot;HRB 3792&quot;), then a Claude Haiku pass for
          special forms (legacy &quot;HRN&quot; prefix, embedded court text) the deterministic
          pass can&apos;t handle. Junk values (checked by Quality Analysis&apos;s Register-Nr.
          check) are excluded - this stage never invents a number for a value that isn&apos;t one.
          Changes are proposals only; review and explicitly accept below.
        </p>
      </div>

      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}

      <Card>
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500/40"
              />
              Use Claude Haiku for special forms
            </label>
            <Button onClick={handleRun} disabled={running}>
              <PlayCircle className="h-4 w-4" />
              {running ? "Running…" : "Run Cleansing"}
            </Button>
          </div>

          {summary && (
            <p className="text-sm text-ink-600">
              {summary.filled} filled value(s) · {summary.junk} junk (unchanged, see Quality) ·{" "}
              {summary.canonical} already canonical · {summary.std} standardized · {summary.llm_candidates}{" "}
              LLM candidate(s), {summary.llm_done} resolved
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-ink-100 pt-4">
            <Button variant="secondary" size="sm" onClick={() => handleAccept(["HIGH"])} disabled={accepting !== null}>
              <Check className="h-3.5 w-3.5" />
              {accepting === "HIGH" ? "…" : "Accept all High"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleAccept(["HIGH", "MEDIUM"])}
              disabled={accepting !== null}
            >
              <Check className="h-3.5 w-3.5" />
              {accepting === "HIGH,MEDIUM" ? "…" : "Accept High + Medium"}
            </Button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Proposals ({proposals.length})</CardTitle>
        </CardHeader>
        <CardBody>
          {proposals.length === 0 ? (
            <EmptyState title="No open proposals" description="Run Cleansing above to generate proposals." />
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>IDParty</Th>
                  <Th>Company</Th>
                  <Th>Country</Th>
                  <Th>Alt</Th>
                  <Th>Neu</Th>
                  <Th>Stufe</Th>
                  <Th>Confidence</Th>
                  <Th>Begruendung</Th>
                </Tr>
              </Thead>
              <Tbody>
                {proposals.slice(0, 200).map((p) => (
                  <Tr key={p.id}>
                    <Td>{p.IDParty}</Td>
                    <Td>{p.CompanyName}</Td>
                    <Td>{p.CountryCode}</Td>
                    <Td>{p.RegisterNumber_Alt}</Td>
                    <Td>{p.RegisterNumber_Neu}</Td>
                    <Td>{p.Stufe}</Td>
                    <Td>
                      <Badge tone={CONFIDENCE_TONE[p.Confidence] ?? "neutral"}>
                        {CONFIDENCE_LABEL[p.Confidence] ?? p.Confidence}
                      </Badge>
                    </Td>
                    <Td>{p.Begruendung}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardBody>
      </Card>

      <div>
        <Button onClick={handleMarkDone} disabled={busy}>
          <CheckCircle2 className="h-4 w-4" />
          Mark this stage as done
        </Button>
      </div>
    </div>
  );
}
