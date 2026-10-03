"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BarChart3, ListChecks, Wand2 } from "lucide-react";
import {
  fetchProjects,
  listAvailableChecks,
  listDatasets,
  listFindings,
  listMappings,
  type Project,
} from "@/lib/api";
import {
  aggregateScorecards,
  classifyDataset,
  entityNameFromProjectName,
  phaseFromProjectName,
  type AggregateScorecard,
  type Phase,
} from "@/lib/scorecard";
import { Alert, Badge, Card, CardBody, CardDescription, CardHeader, CardTitle, ProgressBar, Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui";

const PHASE_TONE: Record<Phase, "warning" | "brand" | "success" | "neutral"> = {
  "Pre-Deployment": "warning",
  Deployment: "brand",
  "Post-Deployment": "success",
  Unclassified: "neutral",
};

type EntityRow = {
  project: Project;
  phase: Phase;
  entityName: string;
  scorecard: AggregateScorecard;
};

export default function LeadershipRollupPage() {
  const { getToken } = useAuth();
  const [rows, setRows] = useState<EntityRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;
      try {
        const projects = await fetchProjects(token);
        const computed = await Promise.all(
          projects.map(async (project) => {
            const [datasets, mappings] = await Promise.all([
              listDatasets(token, project.id),
              listMappings(token, project.id),
            ]);
            const cards = await Promise.all(
              datasets.map(async (ds) => {
                const [checks, findings] = await Promise.all([
                  listAvailableChecks(token, project.id, ds.id),
                  listFindings(token, project.id, ds.id),
                ]);
                return classifyDataset(ds, checks, findings, mappings);
              }),
            );
            return {
              project,
              phase: phaseFromProjectName(project.name),
              entityName: entityNameFromProjectName(project.name),
              scorecard: aggregateScorecards(cards),
            };
          }),
        );
        setRows(computed);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load leadership rollup.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const groupReadiness =
    rows && rows.length > 0 ? Math.round(rows.reduce((s, r) => s + r.scorecard.readinessPct, 0) / rows.length) : null;
  const totalOpenFindings = rows ? rows.reduce((s, r) => s + r.scorecard.totalOpenFindings, 0) : 0;
  const totalMappingNeeded = rows ? rows.reduce((s, r) => s + r.scorecard.mappingNeeded, 0) : 0;
  const totalTransformation = rows ? rows.reduce((s, r) => s + r.scorecard.transformationFields, 0) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
          <BarChart3 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Leadership Rollup</h1>
          <p className="text-sm text-ink-500">
            Every entity, every domain, one view — readiness, open issues and transformation work, rolled up
            across the Group.
          </p>
        </div>
      </div>

      {error && <Alert tone="danger">{error}</Alert>}

      {groupReadiness !== null && (
        <Card>
          <CardBody className="grid grid-cols-1 gap-6 sm:grid-cols-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Group DQ Readiness</p>
              <p className="mt-1 text-3xl font-semibold text-ink-900">{groupReadiness}%</p>
              <div className="mt-2">
                <ProgressBar value={groupReadiness} />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Open Findings</p>
              <p className="mt-1 text-3xl font-semibold text-ink-900">{totalOpenFindings}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Fields Needing Mapping</p>
              <p className="mt-1 text-3xl font-semibold text-ink-900">{totalMappingNeeded}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Transformation Rules</p>
              <p className="mt-1 text-3xl font-semibold text-ink-900">{totalTransformation}</p>
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-ink-400" />
            Entities
          </CardTitle>
          <CardDescription>Readiness by entity and phase — click through to a domain scorecard.</CardDescription>
        </CardHeader>
        <CardBody>
          {!rows ? (
            <p className="text-sm text-ink-500">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-ink-500">No entities yet.</p>
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>Entity</Th>
                  <Th>Phase</Th>
                  <Th>Readiness</Th>
                  <Th>Open Findings</Th>
                  <Th>Mapping Needed</Th>
                  <Th>Transformation Rules</Th>
                  <Th></Th>
                </Tr>
              </Thead>
              <Tbody>
                {rows.map((r) => (
                  <Tr key={r.project.id}>
                    <Td className="font-medium text-ink-900">{r.entityName}</Td>
                    <Td>
                      <Badge tone={PHASE_TONE[r.phase]}>{r.phase}</Badge>
                    </Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        <span className="w-10 text-sm font-medium">{r.scorecard.readinessPct}%</span>
                        <div className="w-24">
                          <ProgressBar value={r.scorecard.readinessPct} />
                        </div>
                      </div>
                    </Td>
                    <Td>{r.scorecard.totalOpenFindings}</Td>
                    <Td>{r.scorecard.mappingNeeded}</Td>
                    <Td>{r.scorecard.transformationFields}</Td>
                    <Td>
                      <Link
                        href={`/dashboard/projects/${r.project.id}/scorecard`}
                        className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-800"
                      >
                        <Wand2 className="h-3.5 w-3.5" />
                        Scorecard
                      </Link>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
