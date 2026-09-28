"use client";

import Link from "next/link";
import clsx from "clsx";
import { Check, ChevronRight, Lock } from "lucide-react";
import { type Stage, type StageStatus } from "@/lib/api";
import { STAGE_ICONS, STAGE_ROUTES } from "@/lib/stages";

const STATUS_META: Record<StageStatus, { label: string; badge: string }> = {
  locked: { label: "Locked", badge: "bg-ink-100 text-ink-500" },
  in_progress: { label: "In progress", badge: "bg-amber-100 text-amber-700" },
  done: { label: "Done", badge: "bg-emerald-100 text-emerald-700" },
};

export function PipelineStepper({ projectId, stages }: { projectId: string; stages: Stage[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {stages.map((stage) => {
        const route = STAGE_ROUTES[stage.key];
        const clickable = Boolean(route) && stage.status !== "locked";
        const Icon = STAGE_ICONS[stage.key] ?? Check;
        const meta = STATUS_META[stage.status];

        const content = (
          <div
            className={clsx(
              "group flex h-full flex-col gap-3 rounded-xl border p-4 transition-all",
              stage.status === "locked"
                ? "border-ink-200 bg-ink-50/60"
                : "border-ink-200 bg-white hover:border-brand-300 hover:shadow-md hover:shadow-ink-900/5",
              clickable && "cursor-pointer",
            )}
          >
            <div className="flex items-start justify-between">
              <div
                className={clsx(
                  "flex h-10 w-10 items-center justify-center rounded-lg",
                  stage.status === "done"
                    ? "bg-emerald-100 text-emerald-700"
                    : stage.status === "in_progress"
                      ? "bg-brand-100 text-brand-700"
                      : "bg-ink-100 text-ink-400",
                )}
              >
                {stage.status === "locked" ? <Lock className="h-4.5 w-4.5" /> : <Icon className="h-4.5 w-4.5" />}
              </div>
              <span className="text-xs font-medium text-ink-300">
                {String(stage.position + 1).padStart(2, "0")}
              </span>
            </div>
            <div className="flex-1">
              <p
                className={clsx(
                  "text-sm font-semibold",
                  stage.status === "locked" ? "text-ink-400" : "text-ink-900",
                )}
              >
                {stage.label}
              </p>
            </div>
            <div className="flex items-center justify-between">
              <span className={clsx("inline-flex rounded-full px-2 py-0.5 text-xs font-medium", meta.badge)}>
                {meta.label}
              </span>
              {clickable && (
                <ChevronRight className="h-4 w-4 text-ink-300 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-600" />
              )}
            </div>
          </div>
        );

        return (
          <div key={stage.key}>
            {clickable ? (
              <Link href={`/dashboard/projects/${projectId}/${route}`}>{content}</Link>
            ) : (
              content
            )}
          </div>
        );
      })}
    </div>
  );
}
