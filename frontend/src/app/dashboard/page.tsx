"use client";

import { useAuth, useOrganization, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useState } from "react";
import { createProject, fetchProjects, provisionTenant, sanitizeTenantSlug, type Project } from "@/lib/api";

export default function DashboardPage() {
  const { getToken, orgId, isLoaded } = useAuth();
  const { organization, isLoaded: orgIsLoaded } = useOrganization();
  const { user } = useUser();
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  async function reload() {
    const token = await getToken();
    if (!token || !organization) return;
    try {
      // Idempotent - a no-op for an already-provisioned org. Covers every
      // path that lands here with an active-but-unprovisioned org (just
      // created one via the OrganizationSwitcher, switched to one created
      // elsewhere, ...) without needing to hook Clerk's own create flow.
      await provisionTenant(
        token,
        organization.name,
        sanitizeTenantSlug(organization.slug ?? organization.id),
        user?.primaryEmailAddress?.emailAddress ?? "",
      );
      setProjects(await fetchProjects(token));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects.");
    }
  }

  useEffect(() => {
    if (isLoaded && orgId && orgIsLoaded) {
      reload();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, orgId, orgIsLoaded]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await createProject(token, newName.trim());
      setNewName("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setCreating(false);
    }
  }

  if (!isLoaded) return null;

  if (!orgId) {
    return (
      <main style={{ padding: "3rem", maxWidth: 640, margin: "0 auto" }}>
        <h1>Dashboard</h1>
        <p>Select or create an organization to continue.</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 640, margin: "0 auto" }}>
      <h1>Projects</h1>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      <form onSubmit={handleCreate} style={{ display: "flex", gap: "0.5rem", margin: "1rem 0" }}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New migration project name"
          style={{ flex: 1, padding: "0.4rem" }}
        />
        <button type="submit" disabled={creating || !newName.trim()}>
          {creating ? "Creating…" : "Create project"}
        </button>
      </form>

      {!error && projects.length === 0 && <p>No projects yet.</p>}
      <ul>
        {projects.map((project) => {
          const done = project.stages.filter((s) => s.status === "done").length;
          return (
            <li key={project.id}>
              <Link href={`/dashboard/projects/${project.id}`}>{project.name}</Link> — {done}/
              {project.stages.length} stages done
            </li>
          );
        })}
      </ul>
    </main>
  );
}
