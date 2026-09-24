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
