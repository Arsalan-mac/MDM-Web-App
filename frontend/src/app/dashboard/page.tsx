"use client";

import { useAuth, useOrganization, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useState } from "react";
import { FolderKanban, Plus } from "lucide-react";
import { createProject, fetchProjects, provisionTenant, sanitizeTenantSlug, type Project } from "@/lib/api";
import { Button, Card, CardBody, EmptyState, Input, ProgressBar, Alert } from "@/components/ui";

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
      <Card>
        <CardBody>
          <EmptyState
            icon={<FolderKanban className="h-8 w-8" />}
            title="Select or create an organization"
            description="Use the switcher in the sidebar to pick a workspace, or create a new one to get started."
          />
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Projects</h1>
          <p className="mt-1 text-sm text-ink-500">Your data-migration projects for this workspace.</p>
        </div>
      </div>

      <Card>
        <CardBody>
          <form onSubmit={handleCreate} className="flex gap-2">
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New migration project name"
            />
            <Button type="submit" disabled={creating || !newName.trim()} className="whitespace-nowrap">
              <Plus className="h-4 w-4" />
              {creating ? "Creating…" : "Create project"}
            </Button>
          </form>
        </CardBody>
      </Card>

      {error && <Alert tone="danger">{error}</Alert>}

      {!error && projects.length === 0 && (
        <Card>
          <CardBody>
            <EmptyState
              icon={<FolderKanban className="h-8 w-8" />}
              title="No projects yet"
              description="Create your first migration project above to start loading and cleansing data."
            />
          </CardBody>
        </Card>
      )}

      {projects.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => {
            const done = project.stages.filter((s) => s.status === "done").length;
            const pct = (done / project.stages.length) * 100;
            return (
              <Link key={project.id} href={`/dashboard/projects/${project.id}`}>
                <Card className="h-full transition-all hover:border-brand-300 hover:shadow-md hover:shadow-ink-900/5">
                  <CardBody className="flex h-full flex-col gap-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
                        <FolderKanban className="h-4.5 w-4.5" />
                      </div>
                      <p className="font-semibold text-ink-900">{project.name}</p>
                    </div>
                    <div className="mt-auto space-y-1.5">
                      <div className="flex items-center justify-between text-xs text-ink-500">
                        <span>
                          {done}/{project.stages.length} stages done
                        </span>
                        <span>{Math.round(pct)}%</span>
                      </div>
                      <ProgressBar value={pct} />
                    </div>
                  </CardBody>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
