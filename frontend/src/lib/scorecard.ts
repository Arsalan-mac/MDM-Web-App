/**
 * Client-side DQ scorecard aggregation - turns the Check Catalog's existing
 * missing_roles/findings and Mapping Studio's field kinds into the
 * cleansing / mapping / transformation split a Data Domain Owner or
 * Leadership view needs. No new backend endpoint: every number here comes
 * from data the generic Dataset/Check/Mapping engine already computes.
 */

import type { CheckDefinition, CheckFinding, Dataset, Mapping } from "./api";

export type RoleStatus = "mapping_needed" | "cleansing_needed" | "ok";

export type RoleClassification = {
  role: string;
  mapped: boolean;
  column: string | null;
  status: RoleStatus;
  openFindings: number;
};

export type DatasetScorecard = {
  datasetId: string;
  datasetName: string;
  roles: RoleClassification[];
  mappingNeeded: number;
  cleansingNeeded: number;
  ok: number;
  totalOpenFindings: number;
  transformationFields: number;
  readinessPct: number;
};

export function classifyDataset(
  dataset: Dataset,
  checks: CheckDefinition[],
  findings: CheckFinding[],
  mappings: Mapping[],
): DatasetScorecard {
  // Only count roles for checks actually in play for this domain - either
  // fully configured (every required role mapped) or already run (has
  // findings). The Check Catalog always lists every built-in check (by
  // design, no fixed pipeline); counting an untouched check's roles as
  // "mapping needed" would flag checks this domain never intended to use.
  // Scoping on *required* roles only (not "any role, including optional")
  // matters because a widely-shared optional role like country_code would
  // otherwise make an unrelated, unconfigured check (e.g. fiscal_code_format)
  // look "in scope" just because that one shared role happens to be mapped.
  const isMapped = (role: string) => {
    const raw = dataset.role_mapping[role];
    return Array.isArray(raw) ? raw.length > 0 : Boolean(raw);
  };
  const roleSet = new Set<string>();
  for (const c of checks) {
    const requiredMapped = c.required_roles.length > 0 && c.required_roles.every(isMapped);
    const hasFindings = findings.some((f) => f.check_key === c.key);
    if (requiredMapped || hasFindings) {
      for (const r of [...c.required_roles, ...c.optional_roles]) roleSet.add(r);
    }
  }

  const openFindings = findings.filter((f) => f.status === "open");

  const roles: RoleClassification[] = Array.from(roleSet)
    .sort()
    .map((role) => {
      const raw = dataset.role_mapping[role];
      const column = typeof raw === "string" && raw ? raw : null;
      const mapped = Array.isArray(raw) ? raw.length > 0 : Boolean(raw);
      let status: RoleStatus = "mapping_needed";
      let roleOpenFindings = 0;
      if (mapped) {
        roleOpenFindings = column ? openFindings.filter((f) => f.field === column).length : 0;
        status = roleOpenFindings > 0 ? "cleansing_needed" : "ok";
      }
      return { role, mapped, column, status, openFindings: roleOpenFindings };
    });

  const transformationFields = mappings
    .filter((m) => m.source_dataset_id === dataset.id)
    .reduce((sum, m) => sum + m.fields.filter((f) => f.kind !== "column").length, 0);

  const mappingNeeded = roles.filter((r) => r.status === "mapping_needed").length;
  const cleansingNeeded = roles.filter((r) => r.status === "cleansing_needed").length;
  const ok = roles.filter((r) => r.status === "ok").length;
  const readinessPct = roles.length > 0 ? Math.round((ok / roles.length) * 100) : 100;

  return {
    datasetId: dataset.id,
    datasetName: dataset.name,
    roles,
    mappingNeeded,
    cleansingNeeded,
    ok,
    totalOpenFindings: openFindings.length,
    transformationFields,
    readinessPct,
  };
}

export type AggregateScorecard = {
  totalRoles: number;
  totalOk: number;
  mappingNeeded: number;
  cleansingNeeded: number;
  totalOpenFindings: number;
  transformationFields: number;
  readinessPct: number;
};

export function aggregateScorecards(cards: DatasetScorecard[]): AggregateScorecard {
  const totalRoles = cards.reduce((s, c) => s + c.roles.length, 0);
  const totalOk = cards.reduce((s, c) => s + c.ok, 0);
  const mappingNeeded = cards.reduce((s, c) => s + c.mappingNeeded, 0);
  const cleansingNeeded = cards.reduce((s, c) => s + c.cleansingNeeded, 0);
  const totalOpenFindings = cards.reduce((s, c) => s + c.totalOpenFindings, 0);
  const transformationFields = cards.reduce((s, c) => s + c.transformationFields, 0);
  const readinessPct = totalRoles > 0 ? Math.round((totalOk / totalRoles) * 100) : 100;
  return { totalRoles, totalOk, mappingNeeded, cleansingNeeded, totalOpenFindings, transformationFields, readinessPct };
}

// Order matters: "Post-Deployment" and "Pre-Deployment" both contain the
// substring "Deployment", so the more specific names must be checked first
// or a Post-Deployment entity would be misread as plain Deployment.
const PHASES = ["Pre-Deployment", "Post-Deployment", "Deployment"] as const;
export type Phase = (typeof PHASES)[number] | "Unclassified";

export function phaseFromProjectName(name: string): Phase {
  const match = PHASES.find((p) => name.includes(p));
  return match ?? "Unclassified";
}

export function entityNameFromProjectName(name: string): string {
  const idx = name.search(/\s[-—]\s/);
  return idx === -1 ? name : name.slice(0, idx).trim();
}
