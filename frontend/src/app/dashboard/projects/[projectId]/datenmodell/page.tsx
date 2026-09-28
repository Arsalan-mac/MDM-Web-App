"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Layers } from "lucide-react";
import { setStageStatus } from "@/lib/api";
import { Alert, Button, Card, CardBody } from "@/components/ui";

export default function DatenmodellPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleMarkDone() {
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "datenmodell", "done");
      router.push(`/dashboard/projects/${projectId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update stage.");
    } finally {
      setSaving(false);
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
          <Layers className="h-5 w-5" />
        </div>
        <h1 className="text-2xl font-semibold text-ink-900">Datenmodell-Erweiterung</h1>
      </div>

      <Card>
        <CardBody className="space-y-4 text-sm text-ink-700">
          <p>
            In the original tool this step dynamically added or removed columns at a precise
            position in the client-data table — needed only because SQLite has no positional{" "}
            <code className="rounded bg-ink-100 px-1 py-0.5 text-xs">ADD COLUMN</code>. Postgres
            doesn&apos;t have that limitation, so there&apos;s no dynamic column editor here —
            schema fields are added directly to the data model as the stages that need them are
            built.
          </p>

          <div>
            <h3 className="mb-2 text-sm font-semibold text-ink-900">What&apos;s in the data model</h3>
            <ul className="list-disc space-y-1.5 pl-5">
              <li>
                A <code className="rounded bg-ink-100 px-1 py-0.5 text-xs">SapOverridden</code>{" "}
                flag on every client record — set by the SAP-CARP-Überschreibung stage, and
                excluded from Address Cleansing&apos;s analysis population.
              </li>
              <li>
                An <code className="rounded bg-ink-100 px-1 py-0.5 text-xs">extra</code> field on
                every client record that keeps any column from an uploaded file that isn&apos;t
                part of the standard set — the equivalent of the original&apos;s &quot;add a
                custom column&quot; feature, with nothing to configure ahead of time.
              </li>
              <li>
                STREET / HOUSE_NUM1 / STR_SUPPL1–3 / BUILDING — the Zerlegung (address-splitting)
                output fields.
              </li>
              <li>Name 1–4, FirstName, LastName, AddedDate, RoedlCompanyNumber, TitleCode, LegalFormCode — SAP Template Migration target fields.</li>
            </ul>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold text-ink-900">Deferred</h3>
            <p>REGION — deferred along with the PLZ/City reference-data checks.</p>
          </div>
        </CardBody>
      </Card>

      {error && <Alert tone="danger">{error}</Alert>}

      <Button onClick={handleMarkDone} disabled={saving}>
        {saving ? "Saving…" : "Mark this stage as done"}
      </Button>
    </div>
  );
}
