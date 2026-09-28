import { type ReactNode } from "react";
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";

type Tone = "danger" | "success" | "info";

const TONE_STYLES: Record<Tone, { wrap: string; icon: ReactNode }> = {
  danger: {
    wrap: "bg-red-50 text-red-700 border-red-200",
    icon: <AlertTriangle className="h-4 w-4 shrink-0" />,
  },
  success: {
    wrap: "bg-emerald-50 text-emerald-700 border-emerald-200",
    icon: <CheckCircle2 className="h-4 w-4 shrink-0" />,
  },
  info: {
    wrap: "bg-brand-50 text-brand-700 border-brand-200",
    icon: <Info className="h-4 w-4 shrink-0" />,
  },
};

export function Alert({
  tone = "danger",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  const styles = TONE_STYLES[tone];
  return (
    <div
      className={clsx(
        "flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm",
        styles.wrap,
        className,
      )}
    >
      {styles.icon}
      <div>{children}</div>
    </div>
  );
}
