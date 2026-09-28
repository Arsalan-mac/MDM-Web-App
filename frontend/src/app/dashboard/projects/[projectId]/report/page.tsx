"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, BarChart3, Download, Files, FolderOpen, Ghost, MapPinned, Hash, Ruler } from "lucide-react";
import { downloadMandantenCsv, getReportSummary, setStageStatus, type ReportSummary } from "@/lib/api";
import { Alert, Badge, Button, Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui";

function StatCard({ icon: Icon, label, value }: { icon: typeof Files; label: string; value: number }) {
  return (
    <Card>
      <CardBody className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-2xl font-semibold text-ink-900">{value}</div>
          <div className="text-sm text-ink-500">{label}</div>
        </div>
      </CardBody>
    </Card>
  );
}

function FindingRow({
  icon: Icon,
  label,
  count,
  hint,
}: {
  icon: typeof Ruler;
  label: string;
  count: number;
  hint: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-ink-100 py-3 last:border-b-0">
      <div className="flex items-center gap-3">
        <Icon className="h-4 w-4 text-ink-400" />
        <div>
          <p className="text-sm font-medium text-ink-900">{label}</p>
          <p className="text-xs text-ink-500">{hint}</p>
        </div>
      </div>
      <Badge tone={count > 0 ? "warning" : "success"}>{count} open</Badge>
    </div>
  );
}

export default function ReportPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;
      try {
        setSummary(await getReportSummary(token, projectId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load report.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleExport() {
    setExporting(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const blob = await downloadMandantenCsv(token, projectId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "mandanten_export.csv";
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Mandanten exported.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  async function handleMarkDone() {
    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "report", "done");
      router.push(`/dashboard/projects/${projectId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update stage.");
    } finally {
      setBusy(false);
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

      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
          <BarChart3 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Report</h1>
          <p className="text-sm text-ink-500">
            A live snapshot of this project&apos;s data volume and outstanding findings.
          </p>
        </div>
      </div>

      {error && <Alert tone="danger">{error}</Alert>}

      {summary && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard icon={Files} label="Mandanten rows" value={summary.mandant_count} />
            <StatCard icon={FolderOpen} label="Auftraege rows" value={summary.auftrag_count} />
            <StatCard icon={Ghost} label="Quarantined ghost objects" value={summary.ghost_count} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Open findings</CardTitle>
              <CardDescription>
                Proposals still waiting for review — visit the matching stage to accept or resolve
                them.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <FindingRow
                icon={MapPinned}
                label="Junk address findings"
                count={summary.open_findings.junk_address}
                hint="Address Cleansing → Analyse"
              />
              <FindingRow
                icon={Ruler}
                label="Address decomposition proposals"
                count={summary.open_findings.address_decomposition}
                hint="Address Cleansing → Zerlegung"
              />
              <FindingRow
                icon={Hash}
                label="RegisterNumber cleansing proposals"
                count={summary.open_findings.register_cleansing}
                hint="RegisterNumber Cleansing"
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Export</CardTitle>
              <CardDescription>Download this project&apos;s data for offline review or handoff.</CardDescription>
            </CardHeader>
            <CardBody className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={handleExport} disabled={exporting}>
                  <Download className="h-4 w-4" />
                  {exporting ? "Exporting…" : "Export Mandanten (CSV)"}
                </Button>
                <Link
                  href={`/dashboard/projects/${projectId}/sap-template`}
                  className="inline-flex items-center gap-2 rounded-lg border border-ink-300 bg-white px-4 py-2 text-sm font-medium text-ink-800 hover:bg-ink-50"
                >
                  <Download className="h-4 w-4 text-brand-600" />
                  Go to SAP Template workbook download
                </Link>
              </div>
              {message && <Alert tone="success">{message}</Alert>}
            </CardBody>
          </Card>
        </>
      )}

      <Button onClick={handleMarkDone} disabled={busy}>
        {busy ? "Saving…" : "Mark this stage as done"}
      </Button>
    </div>
  );
}
