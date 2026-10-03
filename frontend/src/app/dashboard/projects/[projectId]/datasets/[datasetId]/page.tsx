"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Check, ListChecks, Plus, Table2, Trash2, Wand2, X } from "lucide-react";
import {
  acceptFinding,
  createCustomCheck,
  deleteCustomCheck,
  dismissFinding,
  getDataset,
  listAvailableChecks,
  listCustomChecks,
  listFindings,
  listMappings,
  listRelations,
  listRuleTypes,
  runChecks,
  updateRoleMapping,
  type CheckDefinition,
  type CheckFinding,
  type CustomCheck,
  type CustomCheckRuleType,
  type DatasetDetail,
  type DatasetRelation,
  type Mapping,
} from "@/lib/api";
import { classifyDataset } from "@/lib/scorecard";
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
  Input,
  Label,
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

const RULE_TYPE_LABEL: Record<CustomCheckRuleType, string> = {
  required: "Required (not empty)",
  regex: "Matches a pattern (regex)",
  in_list: "One of a fixed list",
  range: "Within a numeric range",
  unique: "Must be unique",
  cross_dataset_exists: "Must exist in another dataset",
};

const ALL_RULE_TYPES: CustomCheckRuleType[] = [
  "required",
  "regex",
  "in_list",
  "range",
  "unique",
  "cross_dataset_exists",
];

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

function CustomChecksEditor({ dataset, onChanged }: { dataset: DatasetDetail; onChanged: () => void }) {
  const { projectId } = useParams<{ projectId: string; datasetId: string }>();
  const { getToken } = useAuth();

  const [customChecks, setCustomChecks] = useState<CustomCheck[]>([]);
  const [ruleTypes, setRuleTypes] = useState<CustomCheckRuleType[]>([]);
  const [relations, setRelations] = useState<DatasetRelation[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [ruleType, setRuleType] = useState<CustomCheckRuleType>("required");
  const [column, setColumn] = useState("");
  const [pattern, setPattern] = useState("");
  const [valuesText, setValuesText] = useState("");
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const [relationId, setRelationId] = useState("");
  const [severity, setSeverity] = useState<"error" | "warning" | "info">("warning");
  const [saving, setSaving] = useState(false);

  async function load() {
    const token = await getToken();
    if (!token) return;
    try {
      const [cc, rt, rels] = await Promise.all([
        listCustomChecks(token, projectId, dataset.id),
        listRuleTypes(token, projectId),
        listRelations(token, projectId),
      ]);
      setCustomChecks(cc);
      setRuleTypes(rt);
      setRelations(rels.filter((r) => r.from_dataset_id === dataset.id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load custom checks.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset.id]);

  function resetForm() {
    setName("");
    setRuleType("required");
    setColumn("");
    setPattern("");
    setValuesText("");
    setMin("");
    setMax("");
    setRelationId("");
    setSeverity("warning");
  }

  function isValid() {
    if (ruleType === "cross_dataset_exists") return !!relationId;
    if (!column) return false;
    if (ruleType === "regex") return !!pattern;
    if (ruleType === "in_list") return !!valuesText.trim();
    return true;
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid()) return;
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");

      let params: Record<string, unknown>;
      switch (ruleType) {
        case "regex":
          params = { column, pattern };
          break;
        case "in_list":
          params = { column, values: valuesText.split(",").map((v) => v.trim()).filter(Boolean) };
          break;
        case "range":
          params = {
            column,
            min: min.trim() === "" ? null : Number(min),
            max: max.trim() === "" ? null : Number(max),
          };
          break;
        case "cross_dataset_exists":
          params = { relation_id: relationId };
          break;
        default:
          params = { column };
      }

      const label = name.trim() || `${RULE_TYPE_LABEL[ruleType]}${column ? ` — ${column}` : ""}`;
      await createCustomCheck(token, projectId, dataset.id, {
        name: label,
        rule_type: ruleType,
        params,
        severity,
      });
      resetForm();
      await load();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create check.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    const token = await getToken();
    if (!token) return;
    await deleteCustomCheck(token, projectId, dataset.id, id);
    await load();
    onChanged();
  }

  function describe(c: CustomCheck): string {
    const p = c.params as Record<string, unknown>;
    switch (c.rule_type) {
      case "required":
        return `${p.column} must not be empty`;
      case "regex":
        return `${p.column} must match ${p.pattern}`;
      case "in_list":
        return `${p.column} must be one of: ${(p.values as string[] | undefined)?.join(", ")}`;
      case "range":
        return `${p.column} must be between ${p.min ?? "−∞"} and ${p.max ?? "∞"}`;
      case "unique":
        return `${p.column} must be unique`;
      case "cross_dataset_exists": {
        const rel = relations.find((r) => r.id === p.relation_id);
        return rel
          ? `${rel.from_column} must exist in ${rel.to_column} (via "${rel.name}")`
          : "Must exist in the related dataset";
      }
      default:
        return "";
    }
  }

  const availableRuleTypes = ruleTypes.length > 0 ? ruleTypes : ALL_RULE_TYPES;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wand2 className="h-4 w-4 text-ink-400" />
          Custom checks
        </CardTitle>
        <CardDescription>
          Define your own checks — no code required. Once added they show up in the Check Catalog below,
          right alongside the built-in ones.
        </CardDescription>
      </CardHeader>
      <CardBody className="space-y-4">
        {customChecks.length > 0 && (
          <div className="space-y-2">
            {customChecks.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-ink-100 px-3 py-2.5"
              >
                <div>
                  <p className="text-sm font-medium text-ink-900">{c.name}</p>
                  <p className="text-xs text-ink-500">{describe(c)}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge tone={SEVERITY_TONE[c.severity]}>{c.severity}</Badge>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-red-600 hover:bg-red-50"
                    onClick={() => handleDelete(c.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleCreate} className="space-y-3 rounded-lg border border-ink-100 bg-ink-50/40 p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label>Rule type</Label>
              <Select
                value={ruleType}
                onChange={(e) => {
                  setRuleType(e.target.value as CustomCheckRuleType);
                  setColumn("");
                  setPattern("");
                  setValuesText("");
                  setMin("");
                  setMax("");
                  setRelationId("");
                }}
              >
                {availableRuleTypes.map((rt) => (
                  <option key={rt} value={rt}>
                    {RULE_TYPE_LABEL[rt]}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Name (optional)</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. VAT ID required" />
            </div>

            {ruleType === "cross_dataset_exists" ? (
              <div className="sm:col-span-2">
                <Label>Relation</Label>
                <Select value={relationId} onChange={(e) => setRelationId(e.target.value)}>
                  <option value="">— select —</option>
                  {relations.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </Select>
                {relations.length === 0 && (
                  <p className="mt-1 text-xs text-ink-500">
                    No relations start from this dataset yet — create one on the Relations page first.
                  </p>
                )}
              </div>
            ) : (
              <div>
                <Label>Column</Label>
                <Select value={column} onChange={(e) => setColumn(e.target.value)}>
                  <option value="">— select —</option>
                  {dataset.columns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </Select>
              </div>
            )}

            {ruleType === "regex" && (
              <div>
                <Label>Pattern (regex)</Label>
                <Input
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value)}
                  placeholder="e.g. ^[A-Z]{2}\d{9}$"
                />
              </div>
            )}

            {ruleType === "in_list" && (
              <div>
                <Label>Allowed values (comma-separated)</Label>
                <Input
                  value={valuesText}
                  onChange={(e) => setValuesText(e.target.value)}
                  placeholder="e.g. active, inactive, pending"
                />
              </div>
            )}

            {ruleType === "range" && (
              <>
                <div>
                  <Label>Min (optional)</Label>
                  <Input type="number" value={min} onChange={(e) => setMin(e.target.value)} placeholder="e.g. 0" />
                </div>
                <div>
                  <Label>Max (optional)</Label>
                  <Input type="number" value={max} onChange={(e) => setMax(e.target.value)} placeholder="e.g. 120" />
                </div>
              </>
            )}

            <div>
              <Label>Severity</Label>
              <Select value={severity} onChange={(e) => setSeverity(e.target.value as "error" | "warning" | "info")}>
                <option value="error">Error</option>
                <option value="warning">Warning</option>
                <option value="info">Info</option>
              </Select>
            </div>
          </div>
          <Button type="submit" size="sm" disabled={!isValid() || saving}>
            <Plus className="h-4 w-4" />
            {saving ? "Adding…" : "Add check"}
          </Button>
        </form>
        {error && <Alert tone="danger">{error}</Alert>}
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
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [selectedChecks, setSelectedChecks] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function reload() {
    const token = await getToken();
    if (!token) return;
    try {
      const [ds, checkList, findingList, mappingList] = await Promise.all([
        getDataset(token, projectId, datasetId),
        listAvailableChecks(token, projectId, datasetId),
        listFindings(token, projectId, datasetId),
        listMappings(token, projectId),
      ]);
      setDataset(ds);
      setChecks(checkList);
      setFindings(findingList);
      setMappings(mappingList);
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

      {(() => {
        const sc = classifyDataset(dataset, checks, findings, mappings);
        return (
          <Card>
            <CardHeader>
              <CardTitle>Readiness classification</CardTitle>
              <CardDescription>
                Every field this domain cares about, sorted into what&apos;s actually blocking it.
              </CardDescription>
            </CardHeader>
            <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Needs Mapping</p>
                <p className="mt-1 text-2xl font-semibold text-amber-600">{sc.mappingNeeded}</p>
                <p className="mt-1 text-xs text-ink-500">roles with no source column yet</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Needs Cleansing</p>
                <p className="mt-1 text-2xl font-semibold text-red-600">{sc.totalOpenFindings}</p>
                <p className="mt-1 text-xs text-ink-500">open findings on mapped fields</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Needs Transformation</p>
                <p className="mt-1 text-2xl font-semibold text-brand-700">{sc.transformationFields}</p>
                <p className="mt-1 text-xs text-ink-500">derived fields defined in Mapping Studio</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Readiness</p>
                <p className="mt-1 text-2xl font-semibold text-emerald-600">{sc.readinessPct}%</p>
                <p className="mt-1 text-xs text-ink-500">
                  {sc.ok} of {sc.roles.length} roles clean
                </p>
              </div>
            </CardBody>
          </Card>
        );
      })()}

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

      <CustomChecksEditor dataset={dataset} onChanged={reload} />

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
