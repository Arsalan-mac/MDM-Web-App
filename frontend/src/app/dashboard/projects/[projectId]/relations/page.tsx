"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, GitBranch, Plus, Trash2 } from "lucide-react";
import {
  createRelation,
  deleteRelation,
  listDatasets,
  listRelations,
  type Cardinality,
  type Dataset,
  type DatasetRelation,
} from "@/lib/api";
import { Alert, Badge, Button, Card, CardBody, CardDescription, CardHeader, CardTitle, EmptyState, Input, Label, Select } from "@/components/ui";

const CARDINALITY_LABEL: Record<Cardinality, string> = {
  one_to_one: "1 : 1",
  one_to_many: "1 : N",
  many_to_many: "N : N",
};

export default function RelationsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [relations, setRelations] = useState<DatasetRelation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const [name, setName] = useState("");
  const [fromDatasetId, setFromDatasetId] = useState("");
  const [fromColumn, setFromColumn] = useState("");
  const [toDatasetId, setToDatasetId] = useState("");
  const [toColumn, setToColumn] = useState("");
  const [cardinality, setCardinality] = useState<Cardinality>("one_to_many");
  const [saving, setSaving] = useState(false);

  async function reload() {
    const token = await getToken();
    if (!token) return;
    try {
      const [ds, rels] = await Promise.all([listDatasets(token, projectId), listRelations(token, projectId)]);
      setDatasets(ds);
      setRelations(rels);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.");
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const fromDataset = datasets.find((d) => d.id === fromDatasetId);
  const toDataset = datasets.find((d) => d.id === toDatasetId);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!fromDatasetId || !fromColumn || !toDatasetId || !toColumn) return;
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const label =
        name.trim() ||
        `${fromDataset?.name ?? "?"}.${fromColumn} -> ${toDataset?.name ?? "?"}.${toColumn}`;
      await createRelation(token, projectId, {
        name: label,
        from_dataset_id: fromDatasetId,
        from_column: fromColumn,
        to_dataset_id: toDatasetId,
        to_column: toColumn,
        cardinality,
      });
      setName("");
      setFromDatasetId("");
      setFromColumn("");
      setToDatasetId("");
      setToColumn("");
      setCardinality("one_to_many");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create relation.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    const token = await getToken();
    if (!token) return;
    await deleteRelation(token, projectId, id);
    await reload();
  }

  function datasetName(id: string) {
    return datasets.find((d) => d.id === id)?.name ?? "(deleted dataset)";
  }

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
          <GitBranch className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Relations</h1>
          <p className="text-sm text-ink-500">
            Define how your datasets relate — e.g. one Customer to many Sales Areas, like SAP&apos;s KNA1
            to KNVV. Used by cross-dataset checks (and, later, the mapping studio).
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New relation</CardTitle>
          <CardDescription>Pick two datasets and the column that should match between them.</CardDescription>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label>From dataset</Label>
                <Select
                  value={fromDatasetId}
                  onChange={(e) => {
                    setFromDatasetId(e.target.value);
                    setFromColumn("");
                  }}
                >
                  <option value="">— select —</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>From column</Label>
                <Select value={fromColumn} onChange={(e) => setFromColumn(e.target.value)} disabled={!fromDataset}>
                  <option value="">— select —</option>
                  {fromDataset?.columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>To dataset</Label>
                <Select
                  value={toDatasetId}
                  onChange={(e) => {
                    setToDatasetId(e.target.value);
                    setToColumn("");
                  }}
                >
                  <option value="">— select —</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>To column</Label>
                <Select value={toColumn} onChange={(e) => setToColumn(e.target.value)} disabled={!toDataset}>
                  <option value="">— select —</option>
                  {toDataset?.columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Cardinality</Label>
                <Select value={cardinality} onChange={(e) => setCardinality(e.target.value as Cardinality)}>
                  <option value="one_to_one">1 : 1</option>
                  <option value="one_to_many">1 : N</option>
                  <option value="many_to_many">N : N</option>
                </Select>
              </div>
              <div>
                <Label>Name (optional)</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Customer → Sales Areas" />
              </div>
            </div>
            <Button type="submit" disabled={!fromDatasetId || !fromColumn || !toDatasetId || !toColumn || saving}>
              <Plus className="h-4 w-4" />
              {saving ? "Creating…" : "Create relation"}
            </Button>
          </form>
          {error && <Alert tone="danger" className="mt-3">{error}</Alert>}
        </CardBody>
      </Card>

      {loaded && relations.length === 0 && (
        <Card>
          <CardBody>
            <EmptyState
              icon={<GitBranch className="h-8 w-8" />}
              title="No relations yet"
              description="Create one above once you have at least two datasets uploaded."
            />
          </CardBody>
        </Card>
      )}

      {relations.length > 0 && (
        <Card>
          <CardBody className="space-y-3">
            {relations.map((rel) => (
              <div
                key={rel.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-ink-100 px-3 py-2.5"
              >
                <div>
                  <p className="text-sm font-medium text-ink-900">{rel.name}</p>
                  <p className="text-xs text-ink-500">
                    {datasetName(rel.from_dataset_id)}.{rel.from_column} → {datasetName(rel.to_dataset_id)}.
                    {rel.to_column}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge tone="brand">{CARDINALITY_LABEL[rel.cardinality]}</Badge>
                  <Button size="sm" variant="ghost" className="text-red-600 hover:bg-red-50" onClick={() => handleDelete(rel.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
