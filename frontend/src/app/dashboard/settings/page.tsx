"use client";

import { useAuth, useOrganization } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { AlertTriangle, Building2, Check, FolderKanban, Pencil, Trash2, X } from "lucide-react";
import { deleteProject, fetchProjects, renameProject, type Project } from "@/lib/api";
import { Alert, Button, Card, CardBody, CardDescription, CardHeader, CardTitle, EmptyState, Input } from "@/components/ui";

function ProjectRow({
  project,
  onRenamed,
  onDeleted,
}: {
  project: Project;
  onRenamed: (p: Project) => void;
  onDeleted: (id: string) => void;
}) {
  const { getToken } = useAuth();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(project.name);
  const [saving, setSaving] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!name.trim() || name === project.name) {
      setEditing(false);
      setName(project.name);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const updated = await renameProject(token, project.id, name.trim());
      onRenamed(updated);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rename failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      await deleteProject(token, project.id);
      onDeleted(project.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
      setDeleting(false);
    }
  }

  return (
    <div className="border-b border-ink-100 py-3 last:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <FolderKanban className="h-4 w-4" />
          </div>
          {editing ? (
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              className="max-w-xs"
            />
          ) : (
            <span className="truncate text-sm font-medium text-ink-900">{project.name}</span>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {editing ? (
            <>
              <Button size="sm" variant="ghost" onClick={handleSave} disabled={saving}>
                <Check className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setEditing(false);
                  setName(project.name);
                }}
                disabled={saving}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </>
          ) : confirmingDelete ? (
            <>
              <span className="text-xs text-ink-500">Delete permanently?</span>
              <Button size="sm" variant="danger" onClick={handleDelete} disabled={deleting}>
                {deleting ? "Deleting…" : "Confirm"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirmingDelete(false)} disabled={deleting}>
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button size="sm" variant="ghost" className="text-red-600 hover:bg-red-50" onClick={() => setConfirmingDelete(true)}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
      </div>
      {error && (
        <p className="mt-1.5 flex items-center gap-1 text-xs text-red-600">
          <AlertTriangle className="h-3 w-3" />
          {error}
        </p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { getToken, isLoaded, orgId } = useAuth();
  const { organization } = useOrganization();
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!isLoaded || !orgId) return;
    (async () => {
      const token = await getToken();
      if (!token) return;
      try {
        setProjects(await fetchProjects(token));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load projects.");
      } finally {
        setLoaded(true);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, orgId]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-900">Settings</h1>
        <p className="mt-1 text-sm text-ink-500">Manage your workspace and its migration projects.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-ink-400" />
            Workspace
          </CardTitle>
          <CardDescription>
            Organization identity, members, and billing are managed via Clerk on the Team page.
          </CardDescription>
        </CardHeader>
        <CardBody>
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink-600">Name</span>
            <span className="text-sm font-medium text-ink-900">{organization?.name ?? "—"}</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Projects</CardTitle>
          <CardDescription>Rename a project, or permanently delete it and all of its data.</CardDescription>
        </CardHeader>
        <CardBody>
          {error && <Alert tone="danger" className="mb-3">{error}</Alert>}
          {loaded && projects.length === 0 && (
            <EmptyState icon={<FolderKanban className="h-8 w-8" />} title="No projects yet" />
          )}
          {projects.map((project) => (
            <ProjectRow
              key={project.id}
              project={project}
              onRenamed={(updated) =>
                setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
              }
              onDeleted={(id) => setProjects((prev) => prev.filter((p) => p.id !== id))}
            />
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
