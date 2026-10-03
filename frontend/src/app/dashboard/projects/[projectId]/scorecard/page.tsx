"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, BarChart3, GitBranch, Table2, Wand2 } from "lucide-react";
import { getProject, listAvailableChecks, listDatasets, listFindings, listMappings, type Project } from "@/lib/api";
import {
  aggregateScorecards,
  classifyDataset,
  phaseFromProjectName,
  type AggregateScorecard,
  type DatasetScorecard,
  type Phase,
} from "@/lib/scorecard";
import { Alert, Badge, Card, CardBody, CardDescription, CardHeader, CardTitle, ProgressBar } from "@/components/ui";

const PHASE_TONE: Record<Phase, "warning" | "brand" | "success" | "neutral"> = {
  "Pre-Deployment": "warning",
  Deployment: "brand",
  "Post-Deployment": "success",
  Unclassified: "neutral",
};

export default function ProjectScorecardPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [cards, setCards] = useState<DatasetScorecard[] | null>(null);
  const [overall, setOverall] = useState<AggregateScorecard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;
      try {
        const [proj, datasets, mappings] = await Promise.all([
          getProject(token, projectId),
          listDatasets(token, projectId),
          listMappings(token, projectId),
        ]);
        const computed = await Promise.all(
          datasets.map(async (ds) => {
            const [checks, findings] = await Promise.all([
              listAvailableChecks(token, projectId, ds.id),
              listFindings(token, projectId, ds.id),
            ]);
            return classifyDataset(ds, checks, findings, mappings);
          }),
        );
        setProject(proj);
        setCards(computed);
        setOverall(aggregateScorecards(computed));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load scorecard.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const phase = project ? phaseFromProjectName(project.name) : "Unclassified";

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/projects/${projectId}`}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to project
      </Link>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
          <BarChart3 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">{project?.name ?? "Scorecard"}</h1>
          <p className="text-sm text-ink-500">Domain Owner view — readiness, remediation and transformation work.</p>
        </div>
        <Badge tone={PHASE_TONE[phase]}>{phase}</Badge>
      </div>

      {error && <Alert tone="danger">{error}</Alert>}

      {overall && (
        <Card>
          <CardBody className="grid grid-cols-1 gap-6 sm:grid-cols-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Readiness</p>
              <p className="mt-1 text-3xl font-semibold text-ink-900">{overall.readinessPct}%</p>
              <div className="mt-2">
                <ProgressBar value={overall.readinessPct} />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Needs Mapping</p>
              <p className="mt-1 text-3xl font-semibold text-amber-600">{overall.mappingNeeded}</p>
              <p className="mt-1 text-xs text-ink-500">roles with no source column assigned</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Needs Cleansing</p>
              <p className="mt-1 text-3xl font-semibold text-red-600">{overall.totalOpenFindings}</p>
              <p className="mt-1 text-xs text-ink-500">open findings across all checks</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Transformation Rules</p>
              <p className="mt-1 text-3xl font-semibold text-brand-700">{overall.transformationFields}</p>
              <p className="mt-1 text-xs text-ink-500">derived fields defined in Mapping Studio</p>
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>By dataset</CardTitle>
          <CardDescription>Each table in this entity's Business Partner domain, with its own breakdown.</CardDescription>
        </CardHeader>
        <CardBody className="space-y-3">
          {!cards ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : (
            cards.map((c) => (
              <div key={c.datasetId} className="rounded-lg border border-ink-100 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Table2 className="h-4 w-4 text-ink-400" />
                    <Link
                      href={`/dashboard/projects/${projectId}/datasets/${c.datasetId}`}
                      className="font-medium text-ink-900 hover:text-brand-700"
                    >
                      {c.datasetName}
                    </Link>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink-900">{c.readinessPct}%</span>
                    <div className="w-28">
                      <ProgressBar value={c.readinessPct} />
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-xs text-ink-500">
                  <span>
                    <strong className="text-amber-600">{c.mappingNeeded}</strong> mapping needed
                  </span>
                  <span>
                    <strong className="text-red-600">{c.totalOpenFindings}</strong> cleansing findings open
                  </span>
                  <span>
                    <strong className="text-brand-700">{c.transformationFields}</strong> transformation rules
                  </span>
                  <span>
                    <strong className="text-emerald-600">{c.ok}</strong> roles clean
                  </span>
                </div>
              </div>
            ))
          )}
        </CardBody>
      </Card>

      <div className="flex flex-wrap gap-3">
        <Link
          href={`/dashboard/projects/${projectId}/datasets`}
          className="inline-flex items-center gap-2 rounded-lg border border-ink-300 bg-white px-4 py-2 text-sm font-medium text-ink-800 hover:bg-ink-50"
        >
          <Table2 className="h-4 w-4 text-brand-600" />
          Datasets &amp; Checks
        </Link>
        <Link
          href={`/dashboard/projects/${projectId}/relations`}
          className="inline-flex items-center gap-2 rounded-lg border border-ink-300 bg-white px-4 py-2 text-sm font-medium text-ink-800 hover:bg-ink-50"
        >
          <GitBranch className="h-4 w-4 text-brand-600" />
          Relations
        </Link>
        <Link
          href={`/dashboard/projects/${projectId}/mappings`}
          className="inline-flex items-center gap-2 rounded-lg border border-ink-300 bg-white px-4 py-2 text-sm font-medium text-ink-800 hover:bg-ink-50"
        >
          <Wand2 className="h-4 w-4 text-brand-600" />
          Mapping Studio
        </Link>
      </div>
    </div>
  );
}
