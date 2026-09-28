import { type InputHTMLAttributes, type SelectHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={clsx(
        "w-full rounded-lg border border-ink-300 bg-white px-3 py-2 text-sm text-ink-900",
        "placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500",
        "disabled:bg-ink-50 disabled:text-ink-400",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select
      ref={ref}
      className={clsx(
        "w-full rounded-lg border border-ink-300 bg-white px-3 py-2 text-sm text-ink-900",
        "focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500",
        className,
      )}
      {...props}
    />
  ),
);
Select.displayName = "Select";

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={clsx("mb-1.5 block text-xs font-medium text-ink-600", className)}
      {...props}
    />
  );
}
