export type StageStatus = "locked" | "in_progress" | "done";

export type Stage = {
  key: string;
  label: string;
  position: number;
  status: StageStatus;
};

export type Project = {
  id: string;
  name: string;
  stages: Stage[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, `API ${path} failed: ${response.status} ${body}`);
  }

  return response.json() as Promise<T>;
}

/** Like apiFetch, but for multipart/form-data uploads - the browser must set
 * its own Content-Type (with the multipart boundary), so it's omitted here
 * rather than forced to application/json like apiFetch does. */
async function apiUpload<T>(path: string, token: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${path} failed: ${response.status} ${body}`);
  }

  return response.json() as Promise<T>;
}

export function fetchProjects(token: string): Promise<Project[]> {
  return apiFetch<Project[]>("/projects", token);
}

export function createProject(token: string, name: string): Promise<Project> {
  return apiFetch<Project>("/projects", token, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function provisionTenant(token: string, name: string, slug: string, email: string) {
  return apiFetch("/tenants/provision", token, {
    method: "POST",
    body: JSON.stringify({ name, slug, email }),
  });
}

export function getProject(token: string, projectId: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`, token);
}

export type LoadSummary = {
  row_count: number;
  columns: string[];
  preview: Record<string, string | null>[];
};

export function uploadMandanten(token: string, projectId: string, file: File): Promise<LoadSummary> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<LoadSummary>(`/projects/${projectId}/load-data/mandanten/upload`, token, formData);
}

export type ReferenceTable = "auftraege" | "verbundene-parteien" | "mandant-gegner";

export function uploadReferenceTable(
  token: string,
  projectId: string,
  table: ReferenceTable,
  file: File,
): Promise<LoadSummary> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<LoadSummary>(`/projects/${projectId}/load-data/${table}/upload`, token, formData);
}

export type AnalysisSummary = {
  rows_checked: number;
  findings: number;
  by_category: Record<string, number>;
  by_confidence: Record<string, number>;
};

export type JunkAddressFinding = {
  id: string;
  IDParty: string;
  UserCode_Kummerer: string | null;
  CompanyName: string | null;
  Address: string | null;
  City: string | null;
  ZipCode: string | null;
  CountryCode: string | null;
  Reason: string;
  Feld: string;
  Alt: string | null;
  Neu: string | null;
  Kategorie: string;
  Aktion: "ERSETZEN" | "LEEREN" | "MANUELL";
  Confidence: "hoch" | "mittel" | "niedrig" | "";
};

export function runAddressAnalysis(token: string, projectId: string): Promise<AnalysisSummary> {
  return apiFetch<AnalysisSummary>(`/projects/${projectId}/address-cleansing/analyze`, token, {
    method: "POST",
  });
}

export function listAddressJunk(token: string, projectId: string): Promise<JunkAddressFinding[]> {
  return apiFetch<JunkAddressFinding[]>(`/projects/${projectId}/address-cleansing/junk`, token);
}

export async function acceptAddressFinding(token: string, projectId: string, findingId: string): Promise<void> {
  const response = await fetch(
    `${API_URL}/projects/${projectId}/address-cleansing/junk/${findingId}/accept`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, `Accept failed: ${response.status} ${body}`);
  }
}

export type ChatTurn = { role: "user" | "assistant"; content: string };

export async function sendChatMessage(
  token: string,
  projectId: string,
  message: string,
  history: ChatTurn[],
): Promise<string> {
  const { reply } = await apiFetch<{ reply: string }>(`/projects/${projectId}/chat`, token, {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
  return reply;
}

export type GeisterobjekteStatus = { mandant_count: number; ghost_count: number };

export function getGeisterobjekteStatus(token: string, projectId: string): Promise<GeisterobjekteStatus> {
  return apiFetch<GeisterobjekteStatus>(`/projects/${projectId}/geisterobjekte/status`, token);
}

export function quarantineGhosts(token: string, projectId: string): Promise<{ quarantined: number }> {
  return apiFetch(`/projects/${projectId}/geisterobjekte/quarantine`, token, { method: "POST" });
}

export function restoreGhosts(
  token: string,
  projectId: string,
): Promise<{ restored: number; skipped: number }> {
  return apiFetch(`/projects/${projectId}/geisterobjekte/restore`, token, { method: "POST" });
}

export type ConsistencyFinding = { table: string; ghost_rows: number; hint: string };

export function getConsistencyCheck(token: string, projectId: string): Promise<ConsistencyFinding[]> {
  return apiFetch<ConsistencyFinding[]>(`/projects/${projectId}/geisterobjekte/consistency`, token);
}

export function uploadSapStammdaten(
  token: string,
  projectId: string,
  file: File,
): Promise<{ row_count: number; columns: string[]; sap_key_col: string; dup_keys: number }> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload(`/projects/${projectId}/sap-carp/stammdaten/upload`, token, formData);
}

export function uploadFieldMapping(token: string, projectId: string, file: File): Promise<LoadSummary> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<LoadSummary>(`/projects/${projectId}/sap-carp/field-mapping/upload`, token, formData);
}

export type ColMapEntry = { mandant_column: string; sap_column: string; condition: string | null };

export type OverwriteStatus = {
  sap_ok: boolean;
  field_ok: boolean;
  mandant_ok: boolean;
  sap_key_col: string | null;
  mapping_rows: number;
  match_count: number;
  already_flagged: number;
  missing_sap: string[];
  col_map: ColMapEntry[];
};

export function getOverwriteStatus(token: string, projectId: string): Promise<OverwriteStatus> {
  return apiFetch<OverwriteStatus>(`/projects/${projectId}/sap-carp/overwrite/status`, token);
}

export function runOverwrite(
  token: string,
  projectId: string,
  resetFlag: boolean,
): Promise<{ flagged: number; sap_rows: number; reset_flag: boolean }> {
  return apiFetch(`/projects/${projectId}/sap-carp/overwrite/run`, token, {
    method: "POST",
    body: JSON.stringify({ reset_flag: resetFlag }),
  });
}

export type NameDistributionStatus = { affected_rows: number; already_split: number };

export function getNameDistributionStatus(token: string, projectId: string): Promise<NameDistributionStatus> {
  return apiFetch<NameDistributionStatus>(`/projects/${projectId}/sap-carp/name-distribution/status`, token);
}

export function runNameDistribution(
  token: string,
  projectId: string,
  chunkSize: number,
): Promise<{ affected: number; chunk_size: number }> {
  return apiFetch(`/projects/${projectId}/sap-carp/name-distribution/run`, token, {
    method: "POST",
    body: JSON.stringify({ chunk_size: chunkSize }),
  });
}

export type NameSplitStatus = { candidate_count: number; cleanup_count: number };

export function getNameSplitStatus(token: string, projectId: string): Promise<NameSplitStatus> {
  return apiFetch<NameSplitStatus>(`/projects/${projectId}/sap-carp/name-split/status`, token);
}

export type NameSplitPreviewRow = {
  id_party: string;
  company_name: string;
  first_name: string;
  last_name: string;
  method: string;
};

export function previewNameSplit(token: string, projectId: string): Promise<NameSplitPreviewRow[]> {
  return apiFetch<NameSplitPreviewRow[]>(`/projects/${projectId}/sap-carp/name-split/preview`, token, {
    method: "POST",
  });
}

export function applyNameSplit(
  token: string,
  projectId: string,
  entries: { id_party: string; first_name: string; last_name: string }[],
): Promise<{ written: number }> {
  return apiFetch(`/projects/${projectId}/sap-carp/name-split/apply`, token, {
    method: "POST",
    body: JSON.stringify({ entries }),
  });
}

export function clearRedundantCompanyNames(token: string, projectId: string): Promise<{ cleared: number }> {
  return apiFetch(`/projects/${projectId}/sap-carp/name-split/clear-company-name`, token, { method: "POST" });
}

export function setStageStatus(
  token: string,
  projectId: string,
  stageKey: string,
  status: StageStatus,
): Promise<Stage> {
  return apiFetch<Stage>(`/projects/${projectId}/stages/${stageKey}`, token, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
