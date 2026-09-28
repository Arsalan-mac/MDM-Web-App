"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Database, Upload } from "lucide-react";
import { uploadMandanten, uploadReferenceTable, type LoadSummary, type ReferenceTable } from "@/lib/api";
import { Alert, Button, Card, CardBody, CardDescription, CardHeader, CardTitle, Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui";

function ReferenceTableUpload({
  projectId,
  table,
  label,
  description,
}: {
  projectId: string;
  table: ReferenceTable;
  label: string;
  description: string;
}) {
  const { getToken } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [summary, setSummary] = useState<LoadSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setSummary(await uploadReferenceTable(token, projectId, table, file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{label}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardBody className="space-y-3">
        <form onSubmit={handleUpload} className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".csv,.txt,.xlsx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm text-ink-600 file:mr-3 file:rounded-lg file:border file:border-ink-300 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink-700 hover:file:bg-ink-50"
          />
          <Button type="submit" size="sm" disabled={!file || uploading}>
            {uploading ? "Uploading…" : "Start Initial Load"}
          </Button>
        </form>
        {error && <Alert tone="danger">{error}</Alert>}
        {summary && (
          <Alert tone="success">
            Loaded {summary.row_count} rows, {summary.columns.length} columns.
          </Alert>
        )}
      </CardBody>
    </Card>
  );
}

export default function LoadDataPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [summary, setSummary] = useState<LoadSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setSummary(await uploadMandanten(token, projectId, file));
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

      <div>
        <h1 className="text-2xl font-semibold text-ink-900">Load Data — Mandanten (Initial Load)</h1>
        <p className="mt-1 text-sm text-ink-500">
          Upload the client master-data file (.csv, .txt or .xlsx). This replaces the project&apos;s
          Mandanten table entirely — the same &quot;Initial Load&quot; behavior as the original tool.
          Delta upload isn&apos;t ported yet.
        </p>
      </div>

      <Card>
        <CardBody className="space-y-4">
          <form onSubmit={handleUpload} className="flex flex-wrap items-center gap-3">
            <input
              type="file"
              accept=".csv,.txt,.xlsx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm text-ink-600 file:mr-3 file:rounded-lg file:border file:border-ink-300 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink-700 hover:file:bg-ink-50"
            />
            <Button type="submit" disabled={!file || uploading}>
              <Upload className="h-4 w-4" />
              {uploading ? "Uploading…" : "Start Initial Load"}
            </Button>
          </form>

          {error && <Alert tone="danger">{error}</Alert>}

          {summary && (
            <>
              <Alert tone="success">
                Loaded {summary.row_count} rows, {summary.columns.length} columns. The Load Data
                stage is now marked done.
              </Alert>
              <div>
                <p className="mb-2 text-sm font-semibold text-ink-800">Preview (first 5 rows)</p>
                <Table>
                  <Thead>
                    <Tr>
                      {summary.columns.map((col) => (
                        <Th key={col}>{col}</Th>
                      ))}
                    </Tr>
                  </Thead>
                  <Tbody>
                    {summary.preview.map((row, i) => (
                      <Tr key={i}>
                        {summary.columns.map((col) => (
                          <Td key={col}>{row[col] ?? ""}</Td>
                        ))}
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </div>
            </>
          )}
        </CardBody>
      </Card>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-ink-400" />
          <h2 className="text-lg font-semibold text-ink-900">Reference tables</h2>
        </div>
        <p className="text-sm text-ink-500">
          Needed by the Geisterobjekte stage to detect client records with no connection to any
          order, related party, or opponent.
        </p>

        <div className="space-y-4">
          <ReferenceTableUpload
            projectId={projectId}
            table="auftraege"
            label="Auftraege (client engagements)"
            description="Columns: IDProject, IDParty, ProjectNumber, Year, AssessmentYear."
          />
          <ReferenceTableUpload
            projectId={projectId}
            table="verbundene-parteien"
            label="VERBUNDENE_PARTEIEN (connected parties)"
            description="Columns: IDParty, IDParty_Related."
          />
          <ReferenceTableUpload
            projectId={projectId}
            table="mandant-gegner"
            label="MANDANT_GEGNER (opponent relationships)"
            description='Columns: "Client - IDParty", "Opponent - IDParty".'
          />
        </div>
      </div>
    </div>
  );
}
