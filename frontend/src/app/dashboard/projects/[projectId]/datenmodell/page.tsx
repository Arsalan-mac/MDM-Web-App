"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { setStageStatus } from "@/lib/api";

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
    <main style={{ padding: "3rem", maxWidth: 700, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>🧩 Datenmodell-Erweiterung</h1>

      <p>
        In the original tool this step dynamically added or removed columns at a precise
        position in the client-data table — needed only because SQLite has no positional
        <code> ADD COLUMN</code>. Postgres doesn&apos;t have that limitation, so there&apos;s
        no dynamic column editor here — schema fields are added directly to the data model as
        the stages that need them are built.
      </p>

      <h3>What&apos;s already in place</h3>
      <ul>
        <li>
          A <code>SapOverridden</code> flag on every client record — set by the (not yet
          built) SAP-CARP-Überschreibung stage, and already excluded from Address
          Cleansing&apos;s analysis population.
        </li>
        <li>
          An <code>extra</code> field on every client record that keeps any column from an
          uploaded file that isn&apos;t part of the standard set — the equivalent of the
          original&apos;s &quot;add a custom column&quot; feature, with nothing to configure
          ahead of time.
        </li>
      </ul>

      <h3>Planned, added when their stage is built</h3>
      <ul>
        <li>STREET / HOUSE_NUM1 / STR_SUPPL1–3 / BUILDING — the Zerlegung (address-splitting) output fields.</li>
        <li>Name 1–4, Name_First, Name_Last, Telefon — SAP Template Migration target fields.</li>
        <li>REGION — deferred along with the PLZ/City reference-data checks.</li>
      </ul>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      <button onClick={handleMarkDone} disabled={saving}>
        {saving ? "Saving…" : "Mark this stage as done"}
      </button>
    </main>
  );
}
