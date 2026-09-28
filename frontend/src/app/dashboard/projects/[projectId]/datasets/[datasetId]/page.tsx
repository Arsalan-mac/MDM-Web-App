"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Check, ListChecks, Table2, X } from "lucide-react";
import {
  acceptFinding,
  dismissFinding,
  getDataset,
  listAvailableChecks,
  listFindings,
  runChecks,
  updateRoleMapping,
  type CheckDefinition,
  type CheckFinding,
  type DatasetDetail,
} from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  Select,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@/components/ui";

const MULTI_VALUE_ROLES = new Set(["match_fields", "required_fields"]);

const SEVERITY_TONE: Record<CheckFinding["severity"], "danger" | "warning" | "brand"> = {
  error: "danger",
  warning: "warning",
  info: "brand",
};

function RoleMappingEditor({
  dataset,
  checks,
  onSaved,
}: {
  dataset: DatasetDetail;
  checks: CheckDefinition[];
  onSaved: (mapping: Record<string, string | string[]>) => void;
}) {
  const { projectId, datasetId } = useParams<{ projectId: string; datasetId: string }>();
  const { getToken } = useAuth();
  const [draft, setDraft] = useState<Record<string, string | string[]>>(dataset.role_mapping);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roles = Array.from(
    new Set(checks.flatMap((c) => [...c.required_roles, ...c.optional_roles])),
  ).sort();

  function setSingle(role: string, column: string) {
    setDraft((prev) => ({ ...prev, [role]: column }));
  }

  function toggleMulti(role: string, column: string) {
    setDraft((prev) => {
      const current = Array.isArray(prev[role]) ? (prev[role] as string[]) : [];
      const next = current.includes(column) ? current.filter((c) => c !== column) : [...current, column];
      return { ...prev, [role]: next };
    });
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const updated = await updateRoleMapping(token, projectId, datasetId, draft);
      onSaved(updated.role_mapping);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save mapping.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Role mapping</CardTitle>
        <CardDescription>
          Tell the checks which of your dataset&apos;s columns play each role. Only roles used by at
          least one check below are listed.
        </CardDescription>
      </CardHeader>
      <CardBody className="space-y-4">
        {roles.length === 0 && <p className="text-sm text-ink-500">No checks registered.</p>}
        {roles.map((role) => (
          <div key={role} className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-4">
            <div className="w-48 shrink-0 pt-2 text-sm font-medium text-ink-800">{role}</div>
            {MULTI_VALUE_ROLES.has(role) ? (
              <div className="flex flex-1 flex-wrap gap-2">
                {dataset.columns.map((col) => {
                  const selected = Array.isArray(draft[role]) && (draft[role] as string[]).includes(col);
                  return (
                    <button
                      key={col}
                      type="button"
                      onClick={() => toggleMulti(role, col)}
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                        selected
                          ? "border-brand-600 bg-brand-600 text-white"
                          : "border-ink-300 bg-white text-ink-600 hover:bg-ink-50"
                      }`}
                    >
                      {col}
                    </button>
                  );
                })}
              </div>
            ) : (
              <Select
                className="flex-1"
                value={(draft[role] as string) ?? ""}
                onChange={(e) => setSingle(role, e.target.value)}
              >
                <option value="">— not mapped —</option>
                {dataset.columns.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </Select>
            )}
          </div>
        ))}
        {error && <Alert tone="danger">{error}</Alert>}
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save mapping"}
        </Button>
      </CardBody>
    </Card>
  );
}

export default function DatasetDetailPage() {
  const { projectId, datasetId } = useParams<{ projectId: string; datasetId: string }>();
  const { getToken } = useAuth();

  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [checks, setChecks] = useState<CheckDefinition[]>([]);
  const [findings, setFindings] = useState<CheckFinding[]>([]);
  const [selectedChecks, setSelectedChecks] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function reload() {
    const token = await getToken();
    if (!token) return;
    try {
      const [ds, checkList, findingList] = await Promise.all([
        getDataset(token, projectId, datasetId),
        listAvailableChecks(token, projectId, datasetId),
        listFindings(token, projectId, datasetId),
      ]);
      setDataset(ds);
      setChecks(checkList);
      setFindings(findingList);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dataset.");
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, datasetId]);

  function toggleCheck(key: string) {
    setSelectedChecks((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleRun() {
    if (selectedChecks.size === 0) return;
    setRunning(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const { finding_counts } = await runChecks(token, projectId, datasetId, Array.from(selectedChecks));
      const total = Object.values(finding_counts).reduce((a, b) => a + b, 0);
      setMessage(`Ran ${selectedChecks.size} check(s), found ${total} finding(s).`);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run checks.");
    } finally {
      setRunning(false);
    }
  }

  async function handleAccept(findingId: string) {
    const token = await getToken();
    if (!token) return;
    await acceptFinding(token, projectId, datasetId, findingId);
    await reload();
  }

  async function handleDismiss(findingId: string) {
    const token = await getToken();
    if (!token) return;
    await dismissFinding(token, projectId, datasetId, findingId);
    await reload();
  }

  if (!dataset) {
    return (
      <div className="space-y-6">
        {error && <Alert tone="danger">{error}</Alert>}
        {!error && <p className="text-sm text-ink-500">Loading…</p>}
      </div>
    );
  }

  const openFindings = findings.filter((f) => f.status === "open");

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/projects/${projectId}/datasets`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to datasets
      </Link>

      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
          <Table2 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">{dataset.name}</h1>
          <p className="text-sm text-ink-500">
            {dataset.row_count} rows · {dataset.columns.length} columns
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Preview</CardTitle>
          <CardDescription>First {dataset.sample_rows.length} rows, exactly as uploaded.</CardDescription>
        </CardHeader>
        <CardBody>
          <Table>
            <Thead>
              <Tr>
                {dataset.columns.map((col) => (
                  <Th key={col}>{col}</Th>
                ))}
              </Tr>
            </Thead>
            <Tbody>
              {dataset.sample_rows.map((row, i) => (
                <Tr key={i}>
                  {dataset.columns.map((col) => (
                    <Td key={col}>{row[col] ?? ""}</Td>
                  ))}
                </Tr>
              ))}
            </Tbody>
          </Table>
        </CardBody>
      </Card>

      <RoleMappingEditor
        dataset={dataset}
        checks={checks}
        onSaved={(mapping) => {
          setDataset((prev) => (prev ? { ...prev, role_mapping: mapping } : prev));
          reload();
        }}
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-ink-400" />
            Check Catalog
          </CardTitle>
          <CardDescription>
            Pick any checks you want — no fixed order, no locked stages. A check greyed out still needs
            a role mapped above.
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {checks.map((check) => {
              const ready = check.missing_roles.length === 0;
              return (
                <label
                  key={check.key}
                  className={`flex items-start gap-3 rounded-lg border p-3 ${
                    ready ? "border-ink-200 bg-white" : "border-ink-100 bg-ink-50/60 opacity-60"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="mt-1 accent-brand-600"
                    disabled={!ready}
                    checked={selectedChecks.has(check.key)}
                    onChange={() => toggleCheck(check.key)}
                  />
                  <div>
                    <p className="text-sm font-medium text-ink-900">{check.label}</p>
                    <p className="text-xs text-ink-500">{check.description}</p>
                    {!ready && (
                      <p className="mt-1 text-xs text-amber-700">
                        Map: {check.missing_roles.join(", ")}
                      </p>
                    )}
                  </div>
                </label>
              );
            })}
          </div>
          <Button onClick={handleRun} disabled={selectedChecks.size === 0 || running}>
            {running ? "Running…" : `Run ${selectedChecks.size || ""} selected check(s)`}
          </Button>
          {message && <Alert tone="success">{message}</Alert>}
          {error && <Alert tone="danger">{error}</Alert>}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Findings</CardTitle>
          <CardDescription>{openFindings.length} open</CardDescription>
        </CardHeader>
        <CardBody>
          {openFindings.length === 0 ? (
            <EmptyState title="No open findings" description="Run a check above, or everything's clean." />
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>Check</Th>
                  <Th>Row</Th>
                  <Th>Field</Th>
                  <Th>Severity</Th>
                  <Th>Message</Th>
                  <Th>Proposed</Th>
                  <Th></Th>
                </Tr>
              </Thead>
              <Tbody>
                {openFindings.map((f) => (
                  <Tr key={f.id}>
                    <Td>{f.check_key}</Td>
                    <Td>{f.row_key}</Td>
                    <Td>{f.field}</Td>
                    <Td>
                      <Badge tone={SEVERITY_TONE[f.severity]}>{f.severity}</Badge>
                    </Td>
                    <Td>{f.message}</Td>
                    <Td>{f.proposed_value ?? "—"}</Td>
                    <Td>
                      <div className="flex gap-1.5">
                        {f.proposed_value != null && (
                          <Button size="sm" variant="ghost" onClick={() => handleAccept(f.id)}>
                            <Check className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        <Button size="sm" variant="ghost" onClick={() => handleDismiss(f.id)}>
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
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
