"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getProject, type Project, type StageStatus } from "@/lib/api";

const STATUS_LABEL: Record<StageStatus, string> = {
  locked: "🔒 Locked",
  in_progress: "🟡 In progress",
  done: "✅ Done",
};

// Stages with a dedicated page to navigate into once unlocked. Every other
// stage is a placeholder until it's ported in Phase 2 (see docs/ROADMAP.md).
const STAGE_ROUTES: Record<string, string> = {
  load_data: "load-data",
  datenmodell: "datenmodell",
  geisterobjekte: "geisterobjekte",
  address_cleansing: "address-cleansing",
};

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

  return (
    <main style={{ padding: "3rem", maxWidth: 640, margin: "0 auto" }}>
      <p>
        <Link href="/dashboard">← All projects</Link>
      </p>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {!project && !error && <p>Loading…</p>}
      {project && (
        <>
          <h1>{project.name}</h1>
          <p>
            <Link href={`/dashboard/projects/${projectId}/chat`}>💬 Talk to your data</Link>
          </p>
          <ol style={{ listStyle: "none", padding: 0 }}>
            {project.stages.map((stage) => {
              const route = STAGE_ROUTES[stage.key];
              const clickable = route && stage.status !== "locked";
              const row = (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "0.6rem 0.8rem",
                    marginBottom: "4px",
                    borderRadius: 6,
                    background: stage.status === "locked" ? "transparent" : "rgba(127,127,127,0.08)",
                    opacity: stage.status === "locked" ? 0.5 : 1,
                  }}
                >
                  <span>{stage.label}</span>
                  <span>{STATUS_LABEL[stage.status]}</span>
                </div>
              );
              return (
                <li key={stage.key}>
                  {clickable ? (
                    <Link href={`/dashboard/projects/${projectId}/${route}`} style={{ color: "inherit" }}>
                      {row}
                    </Link>
                  ) : (
                    row
                  )}
                </li>
              );
            })}
          </ol>
        </>
      )}
    </main>
  );
}
