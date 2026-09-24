"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import {
  runVatAnalysis,
  runVatDuplicateCheck,
  setStageStatus,
  type QualityReportRow,
  type VatAnalysisResult,
  type VatDuplicateRow,
} from "@/lib/api";

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

export default function TaxCleansingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [vatResult, setVatResult] = useState<VatAnalysisResult | null>(null);
  const [dupResult, setDupResult] = useState<VatDuplicateRow[] | null>(null);

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

  async function handleAnalyze() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const result = await runVatAnalysis(token, projectId);
      setVatResult(result);
      setMessage(
        result.vies_backfilled > 0
          ? `Backfilled ${result.vies_backfilled} VATNumber(s) from ViesNumber. ${result.junk.length} issue(s) found.`
          : `${result.junk.length} issue(s) found.`,
      );
    });
  }

  async function handleDuplicates() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      setDupResult(await runVatDuplicateCheck(token, projectId));
    });
  }

  async function handleMarkDone() {
    await withBusy(async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await setStageStatus(token, projectId, "tax_cleansing", "done");
      router.push(`/dashboard/projects/${projectId}`);
    });
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 1000, margin: "0 auto" }}>
      <p>
        <Link href={`/dashboard/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1>🧾 Tax Cleansing</h1>
      <p style={{ color: "#666" }}>
        💶 VAT-Cleansing: unified VAT analysis (country pattern validation, Swiss/Norwegian/Russian
        format handling) and duplicate detection.
      </p>
      <p style={{ color: "#888", fontSize: "0.85rem" }}>
        Note: this page currently covers VAT-Cleansing only. Steuernummer-Cleansing (Fiscal Code) and
        Migration Preparation are separate, larger follow-up phases - see docs/ROADMAP.md.
      </p>

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <h3 style={{ marginTop: "2rem" }}>Unified VAT Analysis</h3>
      <p style={{ color: "#666" }}>
        3-stage process: backfill empty VATNumber from ViesNumber, syntax check, then pattern
        validation against each country&apos;s VAT format.
      </p>
      <button onClick={handleAnalyze} disabled={busy}>
        🚀 Start Unified VAT Analysis
      </button>

      {vatResult && (
        <>
          {vatResult.ru_precleaning.length > 0 && (
            <div style={{ margin: "1rem 0" }}>
              <h4>🇷🇺 RU pre-cleaning</h4>
              <table style={{ borderCollapse: "collapse", fontSize: "0.85rem" }}>
                <thead>
                  <tr>
                    {["IDParty", "Original", "INN", "KPP", "Reason"].map((h) => (
                      <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {vatResult.ru_precleaning.slice(0, 30).map((r, i) => (
                    <tr key={i}>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.id_party}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.vat_number_original}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.inn_cleaned}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.kpp_cleaned}</td>
                      <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p style={{ marginTop: "1rem" }}>
            {vatResult.junk.length === 0
              ? "✅ All VAT numbers are valid - no syntax or pattern errors!"
              : `❌ ${vatResult.junk.length} VAT error(s) found.`}
          </p>
          {vatResult.junk.length > 0 && (
            <table style={{ borderCollapse: "collapse", fontSize: "0.85rem", width: "100%" }}>
              <thead>
                <tr>
                  {["IDParty", "CompanyName", "Country", "VATNumber", "Reason", "Rule"].map((h) => (
                    <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {vatResult.junk.slice(0, 50).map((r, i) => (
                  <tr key={i}>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.id_party}</td>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.company_name}</td>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.country_code}</td>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.vat_number}</td>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.reason}</td>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.rule_used}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <QualityReportTable rows={vatResult.quality_report} />
        </>
      )}

      <hr style={{ margin: "2.5rem 0" }} />

      <h3>VAT Duplicates</h3>
      <p style={{ color: "#666" }}>Mandanten sharing the same normalized VAT number.</p>
      <button onClick={handleDuplicates} disabled={busy}>
        🚀 Check for Duplicates
      </button>
      {dupResult && (
        <>
          <p style={{ marginTop: "1rem" }}>
            {dupResult.length === 0 ? "✅ No VAT duplicates found." : `❌ ${dupResult.length} duplicate row(s).`}
          </p>
          {dupResult.length > 0 && (
            <table style={{ borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr>
                  {["IDParty", "CompanyName", "VATNumber"].map((h) => (
                    <th key={h} style={{ border: "1px solid #ccc", padding: "3px 8px", textAlign: "left" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dupResult.map((r, i) => (
                  <tr key={i}>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.id_party}</td>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.company_name}</td>
                    <td style={{ border: "1px solid #ccc", padding: "3px 8px" }}>{r.vat_number}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
