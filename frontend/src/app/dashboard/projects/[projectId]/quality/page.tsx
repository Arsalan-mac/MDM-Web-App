"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import {
  runAuftragIdProjectCheck,
  runCommunicationCheck,
  runCompletenessCheck,
  runDateStandardization,
  runFuzzyDuplicateCheck,
  runRegisterNumberCheck,
  runValueCleanup,
  setStageStatus,
  type AuftragIdProjectRow,
  type CommunicationCheck,
  type CompletenessRow,
  type ContactCheck,
  type DateStandardizationResult,
  type FuzzyMatch,
  type QualityReportRow,
  type RegisterNumberCheck,
} from "@/lib/api";

type Tab = "cleanup" | "fuzzy" | "register" | "communication" | "completeness" | "date" | "auftrag";

function QualityReportTable({ rows }: { rows: QualityReportRow[] }) {
  if (rows.length === 0) return null;
  return (
    <table style={{ borderCollapse: "collapse", marginTop: "0.75rem", fontSize: "0.85rem" }}>
      <thead>
        <tr>
          {["Typ", "Clients", "Valid", "Junk", "Empty", "% Valid", "% Junk", "% Empty"].map((h) => (
            <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.type}>
            <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.type}</td>
            <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.total_clients}</td>
            <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.total_valid}</td>
            <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.total_junk}</td>
            <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.total_empty}</td>
            <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.pct_valid}%</td>
            <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.pct_junk}%</td>
            <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.pct_empty}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ContactCheckSection({ label, result }: { label: string; result: ContactCheck }) {
  return (
    <div style={{ margin: "1rem 0" }}>
      <h4 style={{ marginBottom: "0.25rem" }}>{label}</h4>
      {result.issues.length === 0 ? (
        <p style={{ color: "green" }}>✅ OK</p>
      ) : (
        <>
          <p style={{ color: "crimson" }}>❌ {result.issues.length} issue(s)</p>
          <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", width: "100%" }}>
            <thead>
              <tr>
                {["IDParty", "CompanyName", "Value", "Reason"].map((h) => (
                  <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.issues.slice(0, 50).map((issue, i) => (
                <tr key={i}>
                  <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{issue.id_party}</td>
                  <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{issue.company_name}</td>
                  <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{issue.invalid_value}</td>
                  <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{issue.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      <QualityReportTable rows={result.quality_report} />
    </div>
  );
}

export default function QualityPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("cleanup");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [badValues, setBadValues] = useState("(Leer), NULL, -");
  const [fuzzyResult, setFuzzyResult] = useState<FuzzyMatch[] | null>(null);
  const [registerResult, setRegisterResult] = useState<RegisterNumberCheck | null>(null);
  const [commResult, setCommResult] = useState<CommunicationCheck | null>(null);
  const [completenessResult, setCompletenessResult] = useState<CompletenessRow[] | null>(null);
  const [dateResult, setDateResult] = useState<DateStandardizationResult | null>(null);
  const [auftragResult, setAuftragResult] = useState<AuftragIdProjectRow[] | null>(null);

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

  async function handleCleanup() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const values = badValues.split(",").map((v) => v.trim()).filter(Boolean);
      const { cleared } = await runValueCleanup(token, projectId, values);
      setMessage(`Cleared ${cleared} field value(s).`);
    });
  }

  async function handleFuzzy() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setFuzzyResult(await runFuzzyDuplicateCheck(token, projectId));
    });
  }

  async function handleRegister() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setRegisterResult(await runRegisterNumberCheck(token, projectId));
    });
  }

  async function handleCommunication() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setCommResult(await runCommunicationCheck(token, projectId));
    });
  }

  async function handleCompleteness() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setCompletenessResult(await runCompletenessCheck(token, projectId));
    });
  }

  async function handleDate() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setDateResult(await runDateStandardization(token, projectId));
    });
  }

  async function handleAuftrag() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setAuftragResult(await runAuftragIdProjectCheck(token, projectId));
    });
  }

  async function handleMarkDone() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "quality", "done");
      router.push(`/dashboard/projects/${projectId}`);
    });
  }

  const tabs: [Tab, string][] = [
    ["cleanup", "🛠️ DB-Bereinigung"],
    ["fuzzy", "🧠 Fuzzy"],
    ["register", "🏛 Register-Nr."],
    ["communication", "📞 Kommunikation"],
    ["completeness", "✅ Vollständigkeit"],
    ["date", "📅 Datum"],
    ["auftrag", "📋 Aufträge DQ"],
  ];

  return (
    <main style={{ padding: "3rem", maxWidth: 1000, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>🔍 Quality Analysis</h1>
      <p style={{ color: "#666" }}>
        Independent data-quality checks over Mandanten and Aufträge. Each check runs on demand and
        shows its result below - nothing here is auto-saved to a review queue.
      </p>
      <p style={{ color: "#888", fontSize: "0.85rem" }}>
        Note: the original tool&apos;s &quot;Missing ID&quot; check isn&apos;t ported - IDParty is a
        required primary key in this system, so a Mandant record with no IDParty cannot exist here.
      </p>

      <div style={{ display: "flex", gap: "0.5rem", margin: "1.5rem 0", borderBottom: "1px solid #ddd", flexWrap: "wrap" }}>
        {tabs.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              padding: "0.5rem 0.8rem",
              border: "none",
              borderBottom: tab === key ? "2px solid #333" : "2px solid transparent",
              background: "transparent",
              fontWeight: tab === key ? 600 : 400,
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      {tab === "cleanup" && (
        <>
          <h3>DB-Bereinigung</h3>
          <p style={{ color: "#666" }}>Replaces exact-match junk values with empty across every Mandant field.</p>
          <input
            value={badValues}
            onChange={(e) => setBadValues(e.target.value)}
            style={{ width: "100%", padding: "0.4rem", marginBottom: "0.5rem" }}
          />
          <br />
          <button onClick={handleCleanup} disabled={busy}>
            🚀 Start Bereinigung
          </button>
        </>
      )}

      {tab === "fuzzy" && (
        <>
          <h3>🧠 Fuzzy Duplicate Check (ML)</h3>
          <p style={{ color: "#666" }}>TF-IDF + Nearest Neighbors with sub-blocking by country and ZIP prefix.</p>
          <button onClick={handleFuzzy} disabled={busy}>
            🚀 Start Fuzzy Analyse
          </button>
          {fuzzyResult && (
            <>
              <p style={{ marginTop: "1rem" }}>
                {fuzzyResult.length === 0 ? "✅ No fuzzy duplicates found." : `${fuzzyResult.length} match(es) found (top 500).`}
              </p>
              {fuzzyResult.length > 0 && (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ borderCollapse: "collapse", fontSize: "0.8rem" }}>
                    <thead>
                      <tr>
                        {["IDParty I", "Name I", "IDParty J", "Name J", "Country", "Similarity", "Category"].map((h) => (
                          <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {fuzzyResult.slice(0, 50).map((m, i) => (
                        <tr key={i}>
                          <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{m.id_party_i}</td>
                          <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{m.company_name_i}</td>
                          <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{m.id_party_j}</td>
                          <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{m.company_name_j}</td>
                          <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{m.country_code}</td>
                          <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{m.similarity_pct}%</td>
                          <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{m.category}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}

      {tab === "register" && (
        <>
          <h3>🏛 Register Number Analysis</h3>
          <p style={{ color: "#666" }}>
            Checks Handelsregisternummern for placeholders, missing digits, dummy sequences, and
            court/context text. Standardization lives on RegisterNumber Cleansing.
          </p>
          <button onClick={handleRegister} disabled={busy}>
            🚀 Start RegisterNumber Check
          </button>
          {registerResult && (
            <>
              <p style={{ marginTop: "1rem" }}>
                {registerResult.junk.length === 0
                  ? "✅ All register numbers look clean."
                  : `❌ ${registerResult.junk.length} problematic register number(s).`}
              </p>
              {registerResult.junk.length > 0 && (
                <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", width: "100%" }}>
                  <thead>
                    <tr>
                      {["IDParty", "CompanyName", "RegisterNumber", "Reason"].map((h) => (
                        <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {registerResult.junk.slice(0, 50).map((r) => (
                      <tr key={r.id_party}>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.id_party}</td>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.company_name}</td>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.register_number}</td>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <QualityReportTable rows={registerResult.quality_report} />
            </>
          )}
        </>
      )}

      {tab === "communication" && (
        <>
          <h3>📞 Communication Analysis</h3>
          <p style={{ color: "#666" }}>Email · Website · Telefon · Fax</p>
          <button onClick={handleCommunication} disabled={busy}>
            🚀 Start Communication Analysis
          </button>
          {commResult && (
            <>
              <ContactCheckSection label="1. Email" result={commResult.email} />
              <ContactCheckSection label="2. Website" result={commResult.website} />
              <ContactCheckSection label="3. Telefon" result={commResult.phone} />
              <ContactCheckSection label="4. Fax" result={commResult.fax} />
            </>
          )}
        </>
      )}

      {tab === "completeness" && (
        <>
          <h3>✅ Vollständigkeits-Prüfung</h3>
          <p style={{ color: "#666" }}>Fill rate per attribute, split by Organisation and Natürliche Person.</p>
          <button onClick={handleCompleteness} disabled={busy}>
            🚀 Start Check
          </button>
          {completenessResult && (
            <div style={{ overflowX: "auto", marginTop: "1rem" }}>
              <table style={{ borderCollapse: "collapse", fontSize: "0.8rem" }}>
                <thead>
                  <tr>
                    {["Typ", "Attribut", "Check-Type", "Total", "Relevant", "%"].map((h) => (
                      <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {completenessResult.map((r, i) => (
                    <tr key={i}>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.type}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.attribute}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.check_type}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.total_rows}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.count_relevant}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.pct ?? "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {tab === "date" && (
        <>
          <h3>📅 Datums-Standardisierung</h3>
          <p style={{ color: "#666" }}>
            Target format: YYYY-MM-DD. Unlike the other checks on this page, this one writes the
            standardized values back to Mandanten directly.
          </p>
          <button onClick={handleDate} disabled={busy}>
            🚀 Start Datums-Standardisierung
          </button>
          {dateResult && (
            <>
              <p style={{ marginTop: "1rem" }}>✅ {dateResult.updated} field(s) standardized.</p>
              {dateResult.preview.length > 0 && (
                <table style={{ borderCollapse: "collapse", fontSize: "0.85rem" }}>
                  <thead>
                    <tr>
                      {["IDParty", "CompanyName", "Changes"].map((h) => (
                        <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dateResult.preview.slice(0, 20).map((r) => (
                      <tr key={r.id_party}>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.id_party}</td>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.company_name}</td>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>
                          {Object.entries(r.changes)
                            .map(([field, c]) => `${field}: ${c.old ?? ""} → ${c.new}`)
                            .join("; ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </>
      )}

      {tab === "auftrag" && (
        <>
          <h3>🔑 ID-Project Check</h3>
          <p style={{ color: "#666" }}>
            Shows every row where the same (IDParty · ProjectName · AddedDate) has more than one
            distinct ServiceName.
          </p>
          <button onClick={handleAuftrag} disabled={busy}>
            🚀 Start ID-Project Check
          </button>
          {auftragResult && (
            <>
              <p style={{ marginTop: "1rem" }}>
                {auftragResult.length === 0
                  ? "✅ No conflicts found."
                  : `❌ ${auftragResult.length} conflicting row(s).`}
              </p>
              {auftragResult.length > 0 && (
                <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", width: "100%" }}>
                  <thead>
                    <tr>
                      {["IDParty", "ProjectName", "AddedDate", "ServiceName"].map((h) => (
                        <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {auftragResult.map((r, i) => (
                      <tr key={i}>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.id_party}</td>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.project_name}</td>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.added_date}</td>
                        <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.service_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </>
      )}

      <hr style={{ margin: "2.5rem 0" }} />
      <button onClick={handleMarkDone} disabled={busy}>
        Mark this stage as done
      </button>
    </main>
  );
}
