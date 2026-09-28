"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Download, Plus, Sparkles, Trash2, Wand2 } from "lucide-react";
import {
  deleteMapping,
  downloadMappingCsv,
  getMapping,
  listDatasets,
  listRelations,
  previewMapping,
  suggestMapping,
  updateMappingFields,
  type Dataset,
  type DatasetRelation,
  type Mapping,
  type MappingField,
  type MappingFieldKind,
  type MappingPreview,
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

const KIND_LABEL: Record<MappingFieldKind, string> = {
  column: "Copy a column",
  constant: "Fixed value",
  concat: "Join several columns",
  relation_lookup: "Look up via a relation",
  name_split: "Split a name (first/last)",
};

const textareaClassName =
  "w-full rounded-lg border border-ink-300 bg-white px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 " +
  "focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500";

export default function MappingDetailPage() {
  const { projectId, mappingId } = useParams<{ projectId: string; mappingId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [mapping, setMapping] = useState<Mapping | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [relations, setRelations] = useState<DatasetRelation[]>([]);
  const [preview, setPreview] = useState<MappingPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [target, setTarget] = useState("");
  const [kind, setKind] = useState<MappingFieldKind>("column");
  const [column, setColumn] = useState("");
  const [constantValue, setConstantValue] = useState("");
  const [concatColumns, setConcatColumns] = useState<string[]>([]);
  const [concatSeparator, setConcatSeparator] = useState(" ");
  const [relationId, setRelationId] = useState("");
  const [relationColumn, setRelationColumn] = useState("");
  const [namePart, setNamePart] = useState<"first" | "last">("first");
  const [saving, setSaving] = useState(false);

  const [suggestText, setSuggestText] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [suggestions, setSuggestions] = useState<{ target: string; column: string }[] | null>(null);

  async function reload() {
    const token = await getToken();
    if (!token) return;
    try {
      const [m, ds, rels] = await Promise.all([
        getMapping(token, projectId, mappingId),
        listDatasets(token, projectId),
        listRelations(token, projectId),
      ]);
      setMapping(m);
      setDatasets(ds);
      setRelations(rels);
      setError(null);
      try {
        setPreview(await previewMapping(token, projectId, mappingId));
      } catch {
        setPreview(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load mapping.");
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, mappingId]);

  const source = mapping ? datasets.find((d) => d.id === mapping.source_dataset_id) : undefined;
  const fromRelations = mapping ? relations.filter((r) => r.from_dataset_id === mapping.source_dataset_id) : [];
  const chosenRelation = relations.find((r) => r.id === relationId);
  const relatedDataset = chosenRelation ? datasets.find((d) => d.id === chosenRelation.to_dataset_id) : undefined;

  function datasetName(id: string) {
    return datasets.find((d) => d.id === id)?.name ?? "(deleted dataset)";
  }

  function resetForm() {
    setTarget("");
    setKind("column");
    setColumn("");
    setConstantValue("");
    setConcatColumns([]);
    setConcatSeparator(" ");
    setRelationId("");
    setRelationColumn("");
    setNamePart("first");
  }

  function isValid(): boolean {
    if (!target.trim()) return false;
    if (kind === "column") return !!column;
    if (kind === "constant") return true;
    if (kind === "concat") return concatColumns.length > 0;
    if (kind === "relation_lookup") return !!relationId && !!relationColumn;
    if (kind === "name_split") return !!column;
    return false;
  }

  function toggleConcatColumn(col: string) {
    setConcatColumns((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]));
  }

  async function persistFields(fields: MappingField[]) {
    const token = await getToken();
    if (!token) throw new Error("Not signed in.");
    const updated = await updateMappingFields(token, projectId, mappingId, fields);
    setMapping(updated);
    try {
      setPreview(await previewMapping(token, projectId, mappingId));
    } catch {
      setPreview(null);
    }
  }

  async function handleAddField(e: React.FormEvent) {
    e.preventDefault();
    if (!mapping || !isValid()) return;
    setSaving(true);
    setError(null);
    try {
      let field: MappingField;
      if (kind === "column") {
        field = { target: target.trim(), kind, config: { column } };
      } else if (kind === "constant") {
        field = { target: target.trim(), kind, config: { value: constantValue } };
      } else if (kind === "concat") {
        field = { target: target.trim(), kind, config: { columns: concatColumns, separator: concatSeparator } };
      } else if (kind === "relation_lookup") {
        field = { target: target.trim(), kind, config: { relation_id: relationId, column: relationColumn } };
      } else {
        field = { target: target.trim(), kind, config: { column, part: namePart } };
      }
      await persistFields([...mapping.fields, field]);
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add field.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteField(index: number) {
    if (!mapping) return;
    setError(null);
    try {
      await persistFields(mapping.fields.filter((_, i) => i !== index));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove field.");
    }
  }

  async function handleSuggest() {
    if (!mapping) return;
    const targets = Array.from(
      new Set(
        suggestText
          .split(/[\n,]/)
          .map((t) => t.trim())
          .filter(Boolean),
      ),
    );
    if (targets.length === 0) return;
    setSuggesting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await suggestMapping(token, projectId, mapping.source_dataset_id, targets);
      setSuggestions(targets.map((t) => ({ target: t, column: result[t] ?? "" })));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get suggestions.");
    } finally {
      setSuggesting(false);
    }
  }

  async function handleAddSuggested() {
    if (!mapping || !suggestions) return;
    const newFields: MappingField[] = suggestions
      .filter((s) => s.column)
      .map((s) => ({ target: s.target, kind: "column", config: { column: s.column } }));
    if (newFields.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      await persistFields([...mapping.fields, ...newFields]);
      setSuggestions(null);
      setSuggestText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add suggested fields.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDownload() {
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const blob = await downloadMappingCsv(token, projectId, mappingId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${mapping?.name ?? "mapping"}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Exported.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    }
  }

  async function handleDeleteMapping() {
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await deleteMapping(token, projectId, mappingId);
      router.push(`/dashboard/projects/${projectId}/mappings`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete mapping.");
    }
  }

  function describeField(field: MappingField): string {
    const c = field.config as Record<string, unknown>;
    switch (field.kind) {
      case "column":
        return `= ${c.column}`;
      case "constant":
        return `= "${c.value}"`;
      case "concat":
        return `= ${(c.columns as string[]).join(` "${c.separator}" `)}`;
      case "relation_lookup": {
        const rel = relations.find((r) => r.id === c.relation_id);
        return rel ? `= ${datasetName(rel.to_dataset_id)}.${c.column} (via "${rel.name}")` : "= (relation deleted)";
      }
      case "name_split":
        return `= ${c.part === "first" ? "first" : "last"} name from ${c.column}`;
      default:
        return "";
    }
  }

  if (!mapping) {
    return (
      <div className="space-y-6">
        {error && <Alert tone="danger">{error}</Alert>}
        {!error && <p className="text-sm text-ink-500">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/projects/${projectId}/mappings`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to mappings
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <Wand2 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-ink-900">{mapping.name}</h1>
            <p className="text-sm text-ink-500">Source: {source?.name ?? "(deleted dataset)"}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleDownload} disabled={mapping.fields.length === 0}>
            <Download className="h-4 w-4" />
            Export CSV
          </Button>
          <Button variant="ghost" className="text-red-600 hover:bg-red-50" onClick={handleDeleteMapping}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-ink-400" />
            AI-assisted quick add
          </CardTitle>
          <CardDescription>
            Type the output column names you want (one per line, or comma-separated) — Claude will suggest which
            source column each one should copy from. You review and confirm before anything is saved.
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-3">
          <textarea
            className={textareaClassName}
            rows={3}
            value={suggestText}
            onChange={(e) => setSuggestText(e.target.value)}
            placeholder={"e.g.\nCustomerID\nCompanyName\nVATNumber"}
          />
          <Button size="sm" onClick={handleSuggest} disabled={!suggestText.trim() || suggesting}>
            <Sparkles className="h-3.5 w-3.5" />
            {suggesting ? "Thinking…" : "Get suggestions"}
          </Button>

          {suggestions && (
            <div className="space-y-2 rounded-lg border border-ink-100 p-3">
              {suggestions.map((s, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="w-48 shrink-0 text-sm font-medium text-ink-800">{s.target}</span>
                  <Select
                    className="flex-1"
                    value={s.column}
                    onChange={(e) =>
                      setSuggestions((prev) =>
                        prev ? prev.map((p, pi) => (pi === i ? { ...p, column: e.target.value } : p)) : prev,
                      )
                    }
                  >
                    <option value="">— no match, pick manually later —</option>
                    {source?.columns.map((col) => (
                      <option key={col} value={col}>
                        {col}
                      </option>
                    ))}
                  </Select>
                </div>
              ))}
              <Button size="sm" onClick={handleAddSuggested} disabled={saving}>
                <Plus className="h-3.5 w-3.5" />
                Add {suggestions.filter((s) => s.column).length} field(s)
              </Button>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Target fields</CardTitle>
          <CardDescription>The output columns, in order, and where each one's value comes from.</CardDescription>
        </CardHeader>
        <CardBody className="space-y-4">
          {mapping.fields.length > 0 && (
            <div className="space-y-2">
              {mapping.fields.map((f, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between gap-3 rounded-lg border border-ink-100 px-3 py-2.5"
                >
                  <div>
                    <p className="text-sm font-medium text-ink-900">{f.target}</p>
                    <p className="text-xs text-ink-500">{describeField(f)}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge tone="brand">{KIND_LABEL[f.kind]}</Badge>
                    <Button size="sm" variant="ghost" className="text-red-600 hover:bg-red-50" onClick={() => handleDeleteField(i)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <form onSubmit={handleAddField} className="space-y-3 rounded-lg border border-ink-100 bg-ink-50/40 p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Label>Target field name</Label>
                <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="e.g. CustomerID" />
              </div>
              <div>
                <Label>Kind</Label>
                <Select
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value as MappingFieldKind);
                    setColumn("");
                    setConstantValue("");
                    setConcatColumns([]);
                    setRelationId("");
                    setRelationColumn("");
                    setNamePart("first");
                  }}
                >
                  {(Object.keys(KIND_LABEL) as MappingFieldKind[]).map((k) => (
                    <option key={k} value={k}>
                      {KIND_LABEL[k]}
                    </option>
                  ))}
                </Select>
              </div>

              {kind === "column" && (
                <div className="sm:col-span-2">
                  <Label>Source column</Label>
                  <Select value={column} onChange={(e) => setColumn(e.target.value)}>
                    <option value="">— select —</option>
                    {source?.columns.map((col) => (
                      <option key={col} value={col}>
                        {col}
                      </option>
                    ))}
                  </Select>
                </div>
              )}

              {kind === "name_split" && (
                <>
                  <div>
                    <Label>Source column (full name)</Label>
                    <Select value={column} onChange={(e) => setColumn(e.target.value)}>
                      <option value="">— select —</option>
                      {source?.columns.map((col) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Which part?</Label>
                    <Select value={namePart} onChange={(e) => setNamePart(e.target.value as "first" | "last")}>
                      <option value="first">First name</option>
                      <option value="last">Last name</option>
                    </Select>
                  </div>
                  <p className="text-xs text-ink-500 sm:col-span-2">
                    Splits on comma or word boundaries; ambiguous 3+-word names get an AI-assisted split. Add
                    this field twice (once per part) to get both First name and Last name columns.
                  </p>
                </>
              )}

              {kind === "constant" && (
                <div className="sm:col-span-2">
                  <Label>Fixed value</Label>
                  <Input value={constantValue} onChange={(e) => setConstantValue(e.target.value)} placeholder="e.g. DE" />
                </div>
              )}

              {kind === "concat" && (
                <div className="sm:col-span-2 space-y-2">
                  <Label>Source columns to join, in order</Label>
                  <div className="flex flex-wrap gap-2">
                    {source?.columns.map((col) => {
                      const selected = concatColumns.includes(col);
                      return (
                        <button
                          key={col}
                          type="button"
                          onClick={() => toggleConcatColumn(col)}
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
                  <Label>Separator</Label>
                  <Input value={concatSeparator} onChange={(e) => setConcatSeparator(e.target.value)} className="w-24" />
                </div>
              )}

              {kind === "relation_lookup" && (
                <>
                  <div>
                    <Label>Relation</Label>
                    <Select
                      value={relationId}
                      onChange={(e) => {
                        setRelationId(e.target.value);
                        setRelationColumn("");
                      }}
                    >
                      <option value="">— select —</option>
                      {fromRelations.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name}
                        </option>
                      ))}
                    </Select>
                    {fromRelations.length === 0 && (
                      <p className="mt-1 text-xs text-ink-500">
                        No relations start from this dataset — create one on the Relations page first.
                      </p>
                    )}
                  </div>
                  <div>
                    <Label>Column on {relatedDataset?.name ?? "related dataset"}</Label>
                    <Select value={relationColumn} onChange={(e) => setRelationColumn(e.target.value)} disabled={!relatedDataset}>
                      <option value="">— select —</option>
                      {relatedDataset?.columns.map((col) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                    </Select>
                  </div>
                </>
              )}
            </div>
            <Button type="submit" size="sm" disabled={!isValid() || saving}>
              <Plus className="h-4 w-4" />
              {saving ? "Adding…" : "Add field"}
            </Button>
          </form>
          {message && <Alert tone="success">{message}</Alert>}
          {error && <Alert tone="danger">{error}</Alert>}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Preview</CardTitle>
          <CardDescription>
            {preview ? `${preview.total_rows} row(s) total, showing the first ${preview.rows.length}.` : "—"}
          </CardDescription>
        </CardHeader>
        <CardBody>
          {!preview || preview.columns.length === 0 ? (
            <p className="text-sm text-ink-500">Add at least one field above to see a preview.</p>
          ) : (
            <Table>
              <Thead>
                <Tr>
                  {preview.columns.map((col) => (
                    <Th key={col}>{col}</Th>
                  ))}
                </Tr>
              </Thead>
              <Tbody>
                {preview.rows.map((row, i) => (
                  <Tr key={i}>
                    {preview.columns.map((col) => (
                      <Td key={col}>{row[col] ?? ""}</Td>
                    ))}
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
