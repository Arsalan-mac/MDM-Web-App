"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Check, PlayCircle, SplitSquareHorizontal } from "lucide-react";
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
import { Alert, Badge, Button, Card, CardBody, CardHeader, CardTitle, EmptyState, Table, Tabs, Tbody, Td, Th, Thead, Tr } from "@/components/ui";

const CONFIDENCE_LABEL: Record<string, string> = {
  hoch: "Hoch",
  mittel: "Mittel",
  niedrig: "Niedrig",
  "": "Manuell",
};

const CONFIDENCE_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  hoch: "success",
  mittel: "warning",
  niedrig: "danger",
  "": "neutral",
};

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
    <div className="space-y-6">
      <Card>
        <CardBody className="space-y-4">
          <p className="text-sm text-ink-500">
            Checks every client&apos;s Address field for placeholders, legal-form/contact-info
            text, missing house numbers, and city/postal-code text embedded in the address.
            PLZ and City checks aren&apos;t ported yet (they need the separate Referenzdaten
            stage) - see the project roadmap.
          </p>

          <Button onClick={handleAnalyze} disabled={analyzing}>
            <PlayCircle className="h-4 w-4" />
            {analyzing ? "Analyzing…" : "Run Adress-Analyse"}
          </Button>

          {error && <Alert tone="danger">{error}</Alert>}
          {summary && (
            <Alert tone="success">
              Checked {summary.rows_checked} records, {summary.findings} findings.
            </Alert>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Findings ({findings.length})</CardTitle>
        </CardHeader>
        <CardBody>
          {findings.length === 0 ? (
            <EmptyState title="No open findings" description="Run the Adress-Analyse above to detect junk addresses." />
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>IDParty</Th>
                  <Th>Company</Th>
                  <Th>Address</Th>
                  <Th>Reason</Th>
                  <Th>Category</Th>
                  <Th>Proposal</Th>
                  <Th>Confidence</Th>
                  <Th></Th>
                </Tr>
              </Thead>
              <Tbody>
                {findings.map((f) => (
                  <Tr key={f.id}>
                    <Td>{f.IDParty}</Td>
                    <Td>{f.CompanyName}</Td>
                    <Td>{f.Address}</Td>
                    <Td>{f.Reason}</Td>
                    <Td>{f.Kategorie}</Td>
                    <Td>{f.Aktion === "MANUELL" ? "—" : f.Aktion === "LEEREN" ? "(leeren)" : f.Neu}</Td>
                    <Td>
                      <Badge tone={CONFIDENCE_TONE[f.Confidence] ?? "neutral"}>
                        {CONFIDENCE_LABEL[f.Confidence] ?? f.Confidence}
                      </Badge>
                    </Td>
                    <Td>
                      {canAccept(f) ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleAccept(f.id)}
                          disabled={acceptingId === f.id}
                        >
                          <Check className="h-3.5 w-3.5" />
                          {acceptingId === f.id ? "…" : "Accept"}
                        </Button>
                      ) : (
                        <span className="text-xs text-ink-400">manual</span>
                      )}
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
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
    <div className="space-y-6">
      <Card>
        <CardBody className="space-y-4">
          <p className="text-sm text-ink-500">
            Splits each client&apos;s free-text Address into SAP&apos;s ADRC target fields
            (STREET / HOUSE_NUM1 / STR_SUPPL1-3 / BUILDING) with a staged regex parser, falling
            back to a Claude Haiku batch call for addresses it can&apos;t confidently split.
            Junk addresses (from Adress-Analyse) aren&apos;t excluded - every partner belongs in
            the migration template, even with an incomplete address.
          </p>

          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500/40"
              />
              Use Claude Haiku for complex/uncertain cases
            </label>
            <Button onClick={handleRun} disabled={running}>
              <SplitSquareHorizontal className="h-4 w-4" />
              {running ? "Running…" : "Run Zerlegung"}
            </Button>
          </div>

          {error && <Alert tone="danger">{error}</Alert>}
          {message && <Alert tone="success">{message}</Alert>}

          {summary && (
            <p className="text-sm text-ink-600">
              {summary.candidates} candidate(s) · {summary.sent_to_llm} sent to Claude ({summary.llm_resolved}{" "}
              resolved) · by confidence:{" "}
              {Object.entries(summary.by_confidence)
                .map(([k, v]) => `${k || "manuell"}=${v}`)
                .join(", ")}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-4 border-t border-ink-100 pt-4">
            <label className="flex items-center gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={spellOut}
                onChange={(e) => setSpellOut(e.target.checked)}
                className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500/40"
              />
              Spell out &quot;Str.&quot; → &quot;Straße&quot;/&quot;Strasse&quot; where available
            </label>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleAcceptConfidences(["hoch"])}
              disabled={accepting !== null}
            >
              <Check className="h-3.5 w-3.5" />
              {accepting === "hoch" ? "…" : "Accept all Hoch"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleAcceptConfidences(["hoch", "mittel"])}
              disabled={accepting !== null}
            >
              <Check className="h-3.5 w-3.5" />
              {accepting === "hoch,mittel" ? "…" : "Accept Hoch + Mittel"}
            </Button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Proposals ({results.length})</CardTitle>
        </CardHeader>
        <CardBody>
          {results.length === 0 ? (
            <EmptyState title="No open proposals" description="Run Zerlegung above to generate proposals." />
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>IDParty</Th>
                  <Th>Address</Th>
                  <Th>STREET</Th>
                  <Th>HOUSE_NUM1</Th>
                  <Th>STR_SUPPL1</Th>
                  <Th>BUILDING</Th>
                  <Th>Method</Th>
                  <Th>Confidence</Th>
                  <Th>Hinweis</Th>
                </Tr>
              </Thead>
              <Tbody>
                {results.slice(0, 200).map((r) => (
                  <Tr key={r.id}>
                    <Td>{r.IDParty}</Td>
                    <Td>{r.Address}</Td>
                    <Td>{r.STREET}</Td>
                    <Td>{r.HOUSE_NUM1}</Td>
                    <Td>{r.STR_SUPPL1}</Td>
                    <Td>{r.BUILDING}</Td>
                    <Td>{r.ParseMethod}</Td>
                    <Td>
                      <Badge tone={CONFIDENCE_TONE[r.Confidence] ?? "neutral"}>
                        {CONFIDENCE_LABEL[r.Confidence] ?? r.Confidence}
                      </Badge>
                    </Td>
                    <Td>{r.Hinweis}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

export default function AddressCleansingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [tab, setTab] = useState<Tab>("analyse");

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
        <h1 className="text-2xl font-semibold text-ink-900">Adress-Cleansing</h1>
      </div>

      <Tabs
        items={[
          { key: "analyse", label: "Adress-Analyse" },
          { key: "zerlegung", label: "Zerlegung" },
        ]}
        active={tab}
        onChange={(key) => setTab(key as Tab)}
      />

      {tab === "analyse" && <AdressAnalyseTab projectId={projectId} />}
      {tab === "zerlegung" && <ZerlegungTab projectId={projectId} />}
    </div>
  );
}
