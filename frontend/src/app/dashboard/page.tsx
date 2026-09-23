import { auth } from "@clerk/nextjs/server";
import { fetchProjects, type Project } from "@/lib/api";

export default async function DashboardPage() {
  const { getToken, orgId } = await auth();

  if (!orgId) {
    return (
      <main style={{ padding: "3rem", maxWidth: 640, margin: "0 auto" }}>
        <h1>Dashboard</h1>
        <p>Select or create an organization to continue.</p>
      </main>
    );
  }

  const token = await getToken();
  let projects: Project[] = [];
  let error: string | null = null;

  try {
    projects = await fetchProjects(token!);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load projects.";
  }

  return (
    <main style={{ padding: "3rem", maxWidth: 640, margin: "0 auto" }}>
      <h1>Projects</h1>
      {error && (
        <p style={{ color: "crimson" }}>
          {error} — has this organization been provisioned yet? (POST /tenants/provision)
        </p>
      )}
      {!error && projects.length === 0 && <p>No projects yet.</p>}
      <ul>
        {projects.map((project) => {
          const done = project.stages.filter((s) => s.status === "done").length;
          return (
            <li key={project.id}>
              {project.name} — {done}/{project.stages.length} stages done
            </li>
          );
        })}
      </ul>
    </main>
  );
}
