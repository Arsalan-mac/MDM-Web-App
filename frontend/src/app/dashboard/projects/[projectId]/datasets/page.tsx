"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Database, GitBranch, Table2, Upload } from "lucide-react";
import { listDatasets, uploadDataset, type Dataset } from "@/lib/api";
import { Alert, Button, Card, CardBody, CardDescription, CardHeader, CardTitle, EmptyState, Input, Label } from "@/components/ui";

export default function DatasetsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [primaryKeyColumn, setPrimaryKeyColumn] = useState("");
  const [uploading, setUploading] = useState(false);

  async function reload() {
    const token = await getToken();
    if (!token) return;
    try {
      setDatasets(await listDatasets(token, projectId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load datasets.");
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !name.trim()) return;
    setUploading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await uploadDataset(token, projectId, file, name.trim(), primaryKeyColumn.trim() || undefined);
      setFile(null);
      setName("");
      setPrimaryKeyColumn("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
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

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <Database className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-ink-900">Datasets</h1>
            <p className="text-sm text-ink-500">
              Upload any file, in any shape — no fixed schema. Map its columns once, then run whichever
              checks you want from the catalog.
            </p>
          </div>
        </div>
        <Link
          href={`/dashboard/projects/${projectId}/relations`}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-ink-300 bg-white px-4 py-2 text-sm font-medium text-ink-800 hover:bg-ink-50"
        >
          <GitBranch className="h-4 w-4 text-brand-600" />
          Relations
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload a dataset</CardTitle>
          <CardDescription>CSV, TXT, or XLSX. Columns are kept exactly as they appear in the file.</CardDescription>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleUpload} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label>Dataset name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Customers" />
              </div>
              <div>
                <Label>Primary key column (optional)</Label>
                <Input
                  value={primaryKeyColumn}
                  onChange={(e) => setPrimaryKeyColumn(e.target.value)}
                  placeholder="e.g. CustomerID — leave blank if none"
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="file"
                accept=".csv,.txt,.xlsx,.xls"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="text-sm text-ink-600 file:mr-3 file:rounded-lg file:border file:border-ink-300 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink-700 hover:file:bg-ink-50"
              />
              <Button type="submit" disabled={!file || !name.trim() || uploading}>
                <Upload className="h-4 w-4" />
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            </div>
          </form>
          {error && <Alert tone="danger" className="mt-3">{error}</Alert>}
        </CardBody>
      </Card>

      {loaded && datasets.length === 0 && !error && (
        <Card>
          <CardBody>
            <EmptyState
              icon={<Table2 className="h-8 w-8" />}
              title="No datasets yet"
              description="Upload a file above to get started — it can be Mandanten, customers, orders, anything."
            />
          </CardBody>
        </Card>
      )}

      {datasets.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {datasets.map((ds) => (
            <Link key={ds.id} href={`/dashboard/projects/${projectId}/datasets/${ds.id}`}>
              <Card className="h-full transition-all hover:border-brand-300 hover:shadow-md hover:shadow-ink-900/5">
                <CardBody className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
                      <Table2 className="h-4.5 w-4.5" />
                    </div>
                    <p className="font-semibold text-ink-900">{ds.name}</p>
                  </div>
                  <div className="text-xs text-ink-500">
                    {ds.row_count} rows · {ds.columns.length} columns
                    {ds.source_filename ? ` · ${ds.source_filename}` : ""}
                  </div>
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
