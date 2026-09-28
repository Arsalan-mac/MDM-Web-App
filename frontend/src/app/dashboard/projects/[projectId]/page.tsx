"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, MessageCircle } from "lucide-react";
import { getProject, type Project } from "@/lib/api";
import { Alert, Badge, ProgressBar } from "@/components/ui";
import { PipelineStepper } from "@/components/PipelineStepper";

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { getToken } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (!token) return;
      try {
        setProject(await getProject(token, projectId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load project.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const done = project ? project.stages.filter((s) => s.status === "done").length : 0;
  const pct = project ? (done / project.stages.length) * 100 : 0;

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-800"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All projects
      </Link>

      {error && <Alert tone="danger">{error}</Alert>}
      {!project && !error && <p className="text-sm text-ink-500">Loading…</p>}

      {project && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-ink-900">{project.name}</h1>
              <div className="mt-2 flex items-center gap-3">
                <Badge tone="brand">
                  {done}/{project.stages.length} stages done
                </Badge>
                <div className="w-40">
                  <ProgressBar value={pct} />
                </div>
              </div>
            </div>
            <Link
              href={`/dashboard/projects/${projectId}/chat`}
              className="inline-flex items-center gap-2 rounded-lg border border-ink-300 bg-white px-4 py-2 text-sm font-medium text-ink-800 hover:bg-ink-50"
            >
              <MessageCircle className="h-4 w-4 text-brand-600" />
              Talk to your data
            </Link>
          </div>

          <PipelineStepper projectId={projectId} stages={project.stages} />
        </>
      )}
    </div>
  );
}
