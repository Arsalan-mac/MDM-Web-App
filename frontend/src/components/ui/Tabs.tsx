"use client";

import clsx from "clsx";

export interface TabItem {
  key: string;
  label: string;
}

export function Tabs({
  items,
  active,
  onChange,
}: {
  items: TabItem[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-1 border-b border-ink-200">
      {items.map((item) => {
        const isActive = item.key === active;
        return (
          <button
            key={item.key}
            type="button"
            onClick={() => onChange(item.key)}
            className={clsx(
              "-mb-px cursor-pointer border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              isActive
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-500 hover:text-ink-800",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
