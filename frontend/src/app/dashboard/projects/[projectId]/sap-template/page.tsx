"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, Download, ListChecks, Package, Search } from "lucide-react";
import {
  downloadSapTemplateWorkbook,
  generateAllSapTemplateSheets,
  listSapTemplateSheets,
  previewSapTemplateSheet,
  setStageStatus,
  type SapTemplateGenerateAll,
  type SapTemplateSheetInfo,
  type SapTemplateSheetPreview,
} from "@/lib/api";
import { Alert, Badge, Button, Card, CardBody, CardHeader, CardTitle, Select, Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui";

export default function SapTemplatePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [sheets, setSheets] = useState<SapTemplateSheetInfo[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>("");
  const [preview, setPreview] = useState<SapTemplateSheetPreview | null>(null);
  const [summary, setSummary] = useState<SapTemplateGenerateAll | null>(null);
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;
      try {
        const s = await listSapTemplateSheets(token, projectId);
        setSheets(s);
        if (s.length > 0) setSelectedSheet(s[0].name);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load sheets.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

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

  async function handlePreview() {
    if (!selectedSheet) return;
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setPreview(await previewSapTemplateSheet(token, projectId, selectedSheet, 5));
    });
  }

  async function handleCheckAll() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setSummary(await generateAllSapTemplateSheets(token, projectId));
    });
  }

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const blob = await downloadSapTemplateWorkbook(token, projectId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "SAP_Migration_Template.xlsx";
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Workbook downloaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  }

  async function handleMarkDone() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "sap_template", "done");
      router.push(`/dashboard/projects/${projectId}`);
    });
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
          <Package className="h-6 w-6 text-brand-600" />
          SAP Template Migration
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Generates SAP Business Partner master-data migration rows from Mandanten: BUT000-General
          (partner master data) and ADRC-Address. Ported as the first slice of this stage - the
          materialized-table sheets (BUT100/BUT0ID/BUT0IS/BUT000-Append), DFKKBPTAXNUM, country
          filtering, CSV export, and anonymization are deferred - see docs/ROADMAP.md.
        </p>
      </div>

      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}

      <Card>
        <CardHeader>
          <CardTitle>Preview (5 rows)</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Select
              value={selectedSheet}
              onChange={(e) => setSelectedSheet(e.target.value)}
              className="max-w-xs"
            >
              {sheets.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name} ({s.field_count} fields)
                </option>
              ))}
            </Select>
            <Button variant="secondary" onClick={handlePreview} disabled={busy || !selectedSheet}>
              <Search className="h-4 w-4" />
              Preview
            </Button>
          </div>

          {preview && (
            <div className="space-y-4">
              <p className="text-sm text-ink-500">
                {preview.total} total row(s) in this sheet · {preview.violations.length} violation(s) among the
                previewed rows
              </p>

              {preview.rows.length > 0 && (
                <Table>
                  <Thead>
                    <Tr>
                      {Object.keys(preview.rows[0]).map((h) => (
                        <Th key={h}>{h}</Th>
                      ))}
                    </Tr>
                  </Thead>
                  <Tbody>
                    {preview.rows.map((row, i) => (
                      <Tr key={i}>
                        {Object.entries(row).map(([field, value]) => {
                          const violated = preview.violations.some((v) => v.row_index === i && v.field === field);
                          return (
                            <Td
                              key={field}
                              className={violated ? "bg-red-50 text-red-800 font-medium" : undefined}
                            >
                              {value}
                            </Td>
                          );
                        })}
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              )}

              {preview.violations.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-ink-900">Violations</h4>
                  <Table>
                    <Thead>
                      <Tr>
                        <Th>IDParty</Th>
                        <Th>Field</Th>
                        <Th>Value</Th>
                        <Th>Allowed length</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {preview.violations.map((v, i) => (
                        <Tr key={i}>
                          <Td>{v.id_party}</Td>
                          <Td>{v.field}</Td>
                          <Td className="bg-red-50 text-red-800 font-medium">{v.value}</Td>
                          <Td>{v.allowed_length}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </div>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Generate</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={handleCheckAll} disabled={busy}>
              <ListChecks className="h-4 w-4" />
              Check all sheets
            </Button>
            <Button onClick={handleDownload} disabled={downloading}>
              <Download className="h-4 w-4" />
              {downloading ? "Generating…" : "Generate & download workbook"}
            </Button>
          </div>

          {summary && (
            <Table>
              <Thead>
                <Tr>
                  <Th>Sheet</Th>
                  <Th>Rows</Th>
                  <Th>Violations</Th>
                </Tr>
              </Thead>
              <Tbody>
                {Object.entries(summary.sheets).map(([name, s]) => (
                  <Tr key={name}>
                    <Td>{name}</Td>
                    <Td>{s.total}</Td>
                    <Td>
                      {s.violation_count > 0 ? (
                        <Badge tone="danger">{s.violation_count}</Badge>
                      ) : (
                        <Badge tone="success">0</Badge>
                      )}
                    </Td>
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
