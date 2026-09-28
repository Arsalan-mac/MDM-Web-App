"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, CheckCircle2, PlayCircle, XCircle } from "lucide-react";
import {
  runAuftragIdProjectCheck,
  runCommunicationCheck,
  runCompletenessCheck,
  runDateStandardization,
  runFuzzyDuplicateCheck,
  runRegisterNumberCheck,
  runValueCleanup,
  setStageStatus,
  type AuftragIdProjectRow,
  type CommunicationCheck,
  type CompletenessRow,
  type ContactCheck,
  type DateStandardizationResult,
  type FuzzyMatch,
  type QualityReportRow,
  type RegisterNumberCheck,
} from "@/lib/api";
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Table,
  Tabs,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@/components/ui";

type Tab = "cleanup" | "fuzzy" | "register" | "communication" | "completeness" | "date" | "auftrag";

function QualityReportTable({ rows }: { rows: QualityReportRow[] }) {
  if (rows.length === 0) return null;
  return (
    <Table className="mt-3">
      <Thead>
        <Tr>
          {["Typ", "Clients", "Valid", "Junk", "Empty", "% Valid", "% Junk", "% Empty"].map((h) => (
            <Th key={h}>{h}</Th>
          ))}
        </Tr>
      </Thead>
      <Tbody>
        {rows.map((r) => (
          <Tr key={r.type}>
            <Td>{r.type}</Td>
            <Td>{r.total_clients}</Td>
            <Td>{r.total_valid}</Td>
            <Td>{r.total_junk}</Td>
            <Td>{r.total_empty}</Td>
            <Td>{r.pct_valid}%</Td>
            <Td>{r.pct_junk}%</Td>
            <Td>{r.pct_empty}%</Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}

function ContactCheckSection({ label, result }: { label: string; result: ContactCheck }) {
  return (
    <div className="space-y-2 border-t border-ink-100 py-4 first:border-t-0 first:pt-0">
      <h4 className="text-sm font-semibold text-ink-900">{label}</h4>
      {result.issues.length === 0 ? (
        <p className="flex items-center gap-1.5 text-sm text-emerald-700">
          <CheckCircle2 className="h-4 w-4" />
          OK
        </p>
      ) : (
        <>
          <p className="flex items-center gap-1.5 text-sm text-red-700">
            <XCircle className="h-4 w-4" />
            {result.issues.length} issue(s)
          </p>
          <Table>
            <Thead>
              <Tr>
                {["IDParty", "CompanyName", "Value", "Reason"].map((h) => (
                  <Th key={h}>{h}</Th>
                ))}
              </Tr>
            </Thead>
            <Tbody>
              {result.issues.slice(0, 50).map((issue, i) => (
                <Tr key={i}>
                  <Td>{issue.id_party}</Td>
                  <Td>{issue.company_name}</Td>
                  <Td>{issue.invalid_value}</Td>
                  <Td>{issue.reason}</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </>
      )}
      <QualityReportTable rows={result.quality_report} />
    </div>
  );
}

export default function QualityPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("cleanup");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [badValues, setBadValues] = useState("(Leer), NULL, -");
  const [fuzzyResult, setFuzzyResult] = useState<FuzzyMatch[] | null>(null);
  const [registerResult, setRegisterResult] = useState<RegisterNumberCheck | null>(null);
  const [commResult, setCommResult] = useState<CommunicationCheck | null>(null);
  const [completenessResult, setCompletenessResult] = useState<CompletenessRow[] | null>(null);
  const [dateResult, setDateResult] = useState<DateStandardizationResult | null>(null);
  const [auftragResult, setAuftragResult] = useState<AuftragIdProjectRow[] | null>(null);

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

  async function handleCleanup() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const values = badValues.split(",").map((v) => v.trim()).filter(Boolean);
      const { cleared } = await runValueCleanup(token, projectId, values);
      setMessage(`Cleared ${cleared} field value(s).`);
    });
  }

  async function handleFuzzy() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setFuzzyResult(await runFuzzyDuplicateCheck(token, projectId));
    });
  }

  async function handleRegister() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setRegisterResult(await runRegisterNumberCheck(token, projectId));
    });
  }

  async function handleCommunication() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setCommResult(await runCommunicationCheck(token, projectId));
    });
  }

  async function handleCompleteness() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setCompletenessResult(await runCompletenessCheck(token, projectId));
    });
  }

  async function handleDate() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setDateResult(await runDateStandardization(token, projectId));
    });
  }

  async function handleAuftrag() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setAuftragResult(await runAuftragIdProjectCheck(token, projectId));
    });
  }

  async function handleMarkDone() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "quality", "done");
      router.push(`/dashboard/projects/${projectId}`);
    });
  }

  const tabs: [Tab, string][] = [
    ["cleanup", "DB-Bereinigung"],
    ["fuzzy", "Fuzzy"],
    ["register", "Register-Nr."],
    ["communication", "Kommunikation"],
    ["completeness", "Vollständigkeit"],
    ["date", "Datum"],
    ["auftrag", "Aufträge DQ"],
  ];

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
        <h1 className="text-2xl font-semibold text-ink-900">Quality Analysis</h1>
        <p className="mt-1 text-sm text-ink-500">
          Independent data-quality checks over Mandanten and Aufträge. Each check runs on demand and
          shows its result below - nothing here is auto-saved to a review queue.
        </p>
        <p className="mt-1 text-xs text-ink-400">
          Note: the original tool&apos;s &quot;Missing ID&quot; check isn&apos;t ported - IDParty is a
          required primary key in this system, so a Mandant record with no IDParty cannot exist here.
        </p>
      </div>

      <Tabs
        items={tabs.map(([key, label]) => ({ key, label }))}
        active={tab}
        onChange={(key) => setTab(key as Tab)}
      />

      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}

      {tab === "cleanup" && (
        <Card>
          <CardHeader>
            <CardTitle>DB-Bereinigung</CardTitle>
            <CardDescription>
              Replaces exact-match junk values with empty across every Mandant field.
            </CardDescription>
          </CardHeader>
          <CardBody className="space-y-3">
            <Input value={badValues} onChange={(e) => setBadValues(e.target.value)} />
            <Button onClick={handleCleanup} disabled={busy}>
              <PlayCircle className="h-4 w-4" />
              Start Bereinigung
            </Button>
          </CardBody>
        </Card>
      )}

      {tab === "fuzzy" && (
        <Card>
          <CardHeader>
            <CardTitle>Fuzzy Duplicate Check (ML)</CardTitle>
            <CardDescription>
              TF-IDF + Nearest Neighbors with sub-blocking by country and ZIP prefix.
            </CardDescription>
          </CardHeader>
          <CardBody className="space-y-3">
            <Button onClick={handleFuzzy} disabled={busy}>
              <PlayCircle className="h-4 w-4" />
              Start Fuzzy Analyse
            </Button>
            {fuzzyResult && (
              <>
                <p className="text-sm text-ink-600">
                  {fuzzyResult.length === 0
                    ? "No fuzzy duplicates found."
                    : `${fuzzyResult.length} match(es) found (top 500).`}
                </p>
                {fuzzyResult.length > 0 && (
                  <Table>
                    <Thead>
                      <Tr>
                        {["IDParty I", "Name I", "IDParty J", "Name J", "Country", "Similarity", "Category"].map(
                          (h) => (
                            <Th key={h}>{h}</Th>
                          ),
                        )}
                      </Tr>
                    </Thead>
                    <Tbody>
                      {fuzzyResult.slice(0, 50).map((m, i) => (
                        <Tr key={i}>
                          <Td>{m.id_party_i}</Td>
                          <Td>{m.company_name_i}</Td>
                          <Td>{m.id_party_j}</Td>
                          <Td>{m.company_name_j}</Td>
                          <Td>{m.country_code}</Td>
                          <Td>{m.similarity_pct}%</Td>
                          <Td>{m.category}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                )}
              </>
            )}
          </CardBody>
        </Card>
      )}

      {tab === "register" && (
        <Card>
          <CardHeader>
            <CardTitle>Register Number Analysis</CardTitle>
            <CardDescription>
              Checks Handelsregisternummern for placeholders, missing digits, dummy sequences, and
              court/context text. Standardization lives on RegisterNumber Cleansing.
            </CardDescription>
          </CardHeader>
          <CardBody className="space-y-3">
            <Button onClick={handleRegister} disabled={busy}>
              <PlayCircle className="h-4 w-4" />
              Start RegisterNumber Check
            </Button>
            {registerResult && (
              <>
                <p className="text-sm text-ink-600">
                  {registerResult.junk.length === 0
                    ? "All register numbers look clean."
                    : `${registerResult.junk.length} problematic register number(s).`}
                </p>
                {registerResult.junk.length > 0 && (
                  <Table>
                    <Thead>
                      <Tr>
                        {["IDParty", "CompanyName", "RegisterNumber", "Reason"].map((h) => (
                          <Th key={h}>{h}</Th>
                        ))}
                      </Tr>
                    </Thead>
                    <Tbody>
                      {registerResult.junk.slice(0, 50).map((r) => (
                        <Tr key={r.id_party}>
                          <Td>{r.id_party}</Td>
                          <Td>{r.company_name}</Td>
                          <Td>{r.register_number}</Td>
                          <Td>{r.reason}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                )}
                <QualityReportTable rows={registerResult.quality_report} />
              </>
            )}
          </CardBody>
        </Card>
      )}

      {tab === "communication" && (
        <Card>
          <CardHeader>
            <CardTitle>Communication Analysis</CardTitle>
            <CardDescription>Email · Website · Telefon · Fax</CardDescription>
          </CardHeader>
          <CardBody className="space-y-3">
            <Button onClick={handleCommunication} disabled={busy}>
              <PlayCircle className="h-4 w-4" />
              Start Communication Analysis
            </Button>
            {commResult && (
              <div>
                <ContactCheckSection label="1. Email" result={commResult.email} />
                <ContactCheckSection label="2. Website" result={commResult.website} />
                <ContactCheckSection label="3. Telefon" result={commResult.phone} />
                <ContactCheckSection label="4. Fax" result={commResult.fax} />
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {tab === "completeness" && (
        <Card>
          <CardHeader>
            <CardTitle>Vollständigkeits-Prüfung</CardTitle>
            <CardDescription>
              Fill rate per attribute, split by Organisation and Natürliche Person.
            </CardDescription>
          </CardHeader>
          <CardBody className="space-y-3">
            <Button onClick={handleCompleteness} disabled={busy}>
              <PlayCircle className="h-4 w-4" />
              Start Check
            </Button>
            {completenessResult && (
              <Table>
                <Thead>
                  <Tr>
                    {["Typ", "Attribut", "Check-Type", "Total", "Relevant", "%"].map((h) => (
                      <Th key={h}>{h}</Th>
                    ))}
                  </Tr>
                </Thead>
                <Tbody>
                  {completenessResult.map((r, i) => (
                    <Tr key={i}>
                      <Td>{r.type}</Td>
                      <Td>{r.attribute}</Td>
                      <Td>{r.check_type}</Td>
                      <Td>{r.total_rows}</Td>
                      <Td>{r.count_relevant}</Td>
                      <Td>{r.pct ?? "n/a"}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            )}
          </CardBody>
        </Card>
      )}

      {tab === "date" && (
        <Card>
          <CardHeader>
            <CardTitle>Datums-Standardisierung</CardTitle>
            <CardDescription>
              Target format: YYYY-MM-DD. Unlike the other checks on this page, this one writes the
              standardized values back to Mandanten directly.
            </CardDescription>
          </CardHeader>
          <CardBody className="space-y-3">
            <Button onClick={handleDate} disabled={busy}>
              <PlayCircle className="h-4 w-4" />
              Start Datums-Standardisierung
            </Button>
            {dateResult && (
              <>
                <p className="flex items-center gap-1.5 text-sm text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" />
                  {dateResult.updated} field(s) standardized.
                </p>
                {dateResult.preview.length > 0 && (
                  <Table>
                    <Thead>
                      <Tr>
                        {["IDParty", "CompanyName", "Changes"].map((h) => (
                          <Th key={h}>{h}</Th>
                        ))}
                      </Tr>
                    </Thead>
                    <Tbody>
                      {dateResult.preview.slice(0, 20).map((r) => (
                        <Tr key={r.id_party}>
                          <Td>{r.id_party}</Td>
                          <Td>{r.company_name}</Td>
                          <Td>
                            {Object.entries(r.changes)
                              .map(([field, c]) => `${field}: ${c.old ?? ""} → ${c.new}`)
                              .join("; ")}
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                )}
              </>
            )}
          </CardBody>
        </Card>
      )}

      {tab === "auftrag" && (
        <Card>
          <CardHeader>
            <CardTitle>ID-Project Check</CardTitle>
            <CardDescription>
              Shows every row where the same (IDParty · ProjectName · AddedDate) has more than one
              distinct ServiceName.
            </CardDescription>
          </CardHeader>
          <CardBody className="space-y-3">
            <Button onClick={handleAuftrag} disabled={busy}>
              <PlayCircle className="h-4 w-4" />
              Start ID-Project Check
            </Button>
            {auftragResult && (
              <>
                <p className="text-sm text-ink-600">
                  {auftragResult.length === 0
                    ? "No conflicts found."
                    : `${auftragResult.length} conflicting row(s).`}
                </p>
                {auftragResult.length > 0 && (
                  <Table>
                    <Thead>
                      <Tr>
                        {["IDParty", "ProjectName", "AddedDate", "ServiceName"].map((h) => (
                          <Th key={h}>{h}</Th>
                        ))}
                      </Tr>
                    </Thead>
                    <Tbody>
                      {auftragResult.map((r, i) => (
                        <Tr key={i}>
                          <Td>{r.id_party}</Td>
                          <Td>{r.project_name}</Td>
                          <Td>{r.added_date}</Td>
                          <Td>{r.service_name}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                )}
              </>
            )}
          </CardBody>
        </Card>
      )}

      <div className="flex justify-end border-t border-ink-200 pt-6">
        <Button variant="secondary" onClick={handleMarkDone} disabled={busy}>
          Mark this stage as done
        </Button>
      </div>
    </div>
  );
}
