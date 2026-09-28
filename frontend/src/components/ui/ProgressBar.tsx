import clsx from "clsx";

export function ProgressBar({ value, className }: { value: number; className?: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-ink-100", className)}>
      <div
        className="h-full rounded-full bg-brand-600 transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
