"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Plus, Wand2 } from "lucide-react";
import { createMapping, listDatasets, listMappings, type Dataset, type Mapping } from "@/lib/api";
import {
  Alert,
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
} from "@/components/ui";

export default function MappingsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const [name, setName] = useState("");
  const [sourceDatasetId, setSourceDatasetId] = useState("");
  const [saving, setSaving] = useState(false);

  async function reload() {
    const token = await getToken();
    if (!token) return;
    try {
      const [ds, maps] = await Promise.all([listDatasets(token, projectId), listMappings(token, projectId)]);
      setDatasets(ds);
      setMappings(maps);
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

  function datasetName(id: string) {
    return datasets.find((d) => d.id === id)?.name ?? "(deleted dataset)";
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !sourceDatasetId) return;
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await createMapping(token, projectId, { name: name.trim(), source_dataset_id: sourceDatasetId, fields: [] });
      setName("");
      setSourceDatasetId("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create mapping.");
    } finally {
      setSaving(false);
    }
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
          <Wand2 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Mapping Studio</h1>
          <p className="text-sm text-ink-500">
            Build a new table out of one of your datasets — copy columns, join in a related dataset, or let AI
            suggest the mapping — then export it as a CSV.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New mapping</CardTitle>
          <CardDescription>Pick a source dataset, then add target fields on the next screen.</CardDescription>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label>Mapping name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. SAP Customer Export" />
              </div>
              <div>
                <Label>Source dataset</Label>
                <Select value={sourceDatasetId} onChange={(e) => setSourceDatasetId(e.target.value)}>
                  <option value="">— select —</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <Button type="submit" disabled={!name.trim() || !sourceDatasetId || saving}>
              <Plus className="h-4 w-4" />
              {saving ? "Creating…" : "Create mapping"}
            </Button>
          </form>
          {error && <Alert tone="danger" className="mt-3">{error}</Alert>}
        </CardBody>
      </Card>

      {loaded && mappings.length === 0 && (
        <Card>
          <CardBody>
            <EmptyState
              icon={<Wand2 className="h-8 w-8" />}
              title="No mappings yet"
              description="Create one above once you have a dataset uploaded."
            />
          </CardBody>
        </Card>
      )}

      {mappings.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {mappings.map((m) => (
            <Link key={m.id} href={`/dashboard/projects/${projectId}/mappings/${m.id}`}>
              <Card className="h-full transition-all hover:border-brand-300 hover:shadow-md hover:shadow-ink-900/5">
                <CardBody className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-ink-900">{m.name}</p>
                    <p className="text-xs text-ink-500">
                      From {datasetName(m.source_dataset_id)} · {m.fields.length} field
                      {m.fields.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-ink-300" />
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
