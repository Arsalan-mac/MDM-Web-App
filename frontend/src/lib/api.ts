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
    throw new Error(`API ${path} failed: ${response.status} ${body}`);
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
    throw new Error(`Accept failed: ${response.status} ${body}`);
  }
}
