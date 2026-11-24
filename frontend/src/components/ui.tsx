import type { ReactNode } from "react";
import { useEffect } from "react";
import { IconAlert, IconChevron, IconClose, IconRefresh, IconSearch } from "./Icons";

type Tone = "teal" | "green" | "amber" | "red" | "blue" | "slate" | "navy";

const toneClasses: Record<Tone, string> = {
  teal: "bg-teal-50 text-teal-700 ring-1 ring-inset ring-teal-600/15",
  green: "bg-signal-green-soft text-signal-green ring-1 ring-inset ring-signal-green/15",
  amber: "bg-signal-amber-soft text-amber-700 ring-1 ring-inset ring-amber-600/20",
  red: "bg-signal-red-soft text-signal-red ring-1 ring-inset ring-red-600/15",
  blue: "bg-signal-blue-soft text-signal-blue ring-1 ring-inset ring-blue-600/15",
  slate: "bg-ink-100 text-ink-700 ring-1 ring-inset ring-ink-500/10",
  navy: "bg-navy-900 text-white ring-1 ring-inset ring-white/10",
};

export function Badge({ tone = "slate", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`chip ${toneClasses[tone]}`}>{children}</span>;
}

export function PriorityBadge({ priority }: { priority: string }) {
  const tone: Tone =
    priority === "P1" ? "red" : priority === "P2" ? "amber" : priority === "P3" ? "blue" : priority === "P4" ? "teal" : "slate";
  return <Badge tone={tone}>{priority}</Badge>;
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const normalized = (status ?? "UNKNOWN").toUpperCase();
  const tone: Tone =
    ["APPROVED", "COMPLETED", "ACTIVE", "INGESTED", "OK", "PASSED"].includes(normalized)
      ? "green"
      : ["PENDING_REVIEW", "DEFERRED", "IN_PROGRESS", "RUNNING"].includes(normalized)
        ? "amber"
        : ["REJECTED", "ESCALATED", "FAILED", "CRITICAL", "RETIRED"].includes(normalized)
          ? "red"
          : ["IN_REVIEW", "OVERRIDDEN"].includes(normalized)
            ? "blue"
            : "slate";
  return <Badge tone={tone}>{normalized.replace(/_/g, " ")}</Badge>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl">
        {eyebrow && <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-teal-700">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900 md:text-[30px]">{title}</h1>
        {description && <p className="mt-2 text-sm leading-6 text-ink-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
  bodyClassName = "p-5",
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`card animate-fade-in ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-300/50 px-5 py-4">
          <div>
            {title && <h2 className="text-sm font-semibold text-ink-900">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-500">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function StatCard({
  label,
  value,
  hint,
  tone = "teal",
  icon,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
  icon?: ReactNode;
}) {
  return (
    <div className="card animate-fade-in p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-500">{label}</p>
        {icon && <span className={`rounded-xl p-2 ${toneClasses[tone]}`}>{icon}</span>}
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-ink-900">{value}</p>
      {hint && <div className="mt-2 text-xs leading-5 text-ink-500">{hint}</div>}
    </div>
  );
}

export function Callout({
  tone = "blue",
  title,
  children,
}: {
  tone?: "blue" | "amber" | "red" | "green" | "slate";
  title?: ReactNode;
  children: ReactNode;
}) {
  const styles = {
    blue: "border-blue-200 bg-signal-blue-soft text-blue-900",
    amber: "border-amber-200 bg-signal-amber-soft text-amber-900",
    red: "border-red-200 bg-signal-red-soft text-red-900",
    green: "border-emerald-200 bg-signal-green-soft text-emerald-900",
    slate: "border-ink-300 bg-ink-50 text-ink-700",
  }[tone];
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm leading-6 ${styles}`}>
      {title && <p className="mb-0.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">{title}</p>}
      {children}
    </div>
  );
}

export function LoadingBlock({ label = "Loading data…", rows = 4 }: { label?: string; rows?: number }) {
  return (
    <div className="card animate-pulse p-5" role="status" aria-label={label}>
      <div className="mb-4 h-4 w-40 rounded bg-ink-100" />
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="h-10 rounded-xl bg-ink-100/80" />
        ))}
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card border-red-200 p-6">
      <div className="flex items-start gap-3">
        <span className="rounded-xl bg-signal-red-soft p-2 text-signal-red">
          <IconAlert className="h-5 w-5" />
        </span>
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-ink-900">This view could not load</h2>
          <p className="mt-1 text-sm leading-6 text-ink-500">{message}</p>
          <p className="mt-2 text-xs text-ink-500">
            Confirm the API is reachable at <span className="font-mono">/health</span> and that the PostgreSQL container is running.
          </p>
          {onRetry && (
            <button type="button" className="btn-ghost mt-4" onClick={onRetry}>
              <IconRefresh className="h-4 w-4" /> Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function EmptyBlock({ title = "No records", children }: { title?: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-ink-300 bg-ink-50/60 px-6 py-10 text-center">
      <p className="text-sm font-semibold text-ink-700">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-lg text-xs leading-5 text-ink-500">{children}</div>}
    </div>
  );
}

export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-1 py-3">
      <p className="text-xs text-ink-500">
        Showing <span className="font-semibold text-ink-700">{total === 0 ? 0 : offset + 1}</span>–
        <span className="font-semibold text-ink-700">{Math.min(offset + limit, total)}</span> of{" "}
        <span className="font-semibold text-ink-700">{total.toLocaleString()}</span>
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="btn-ghost px-3 py-1.5"
          disabled={offset <= 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          <IconChevron className="h-4 w-4 rotate-180" /> Previous
        </button>
        <span className="px-1 text-xs font-medium text-ink-500">
          Page {page} / {pages}
        </span>
        <button
          type="button"
          className="btn-ghost px-3 py-1.5"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next <IconChevron className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-ink-500">{hint}</span>}
    </label>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder = "Search",
  className = "",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={`relative ${className}`}>
      <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" />
      <input
        className="input pl-9"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        aria-label={placeholder}
      />
    </div>
  );
}

export function MeterBar({
  value,
  max = 1,
  tone = "teal",
  height = "h-1.5",
}: {
  value: number | null | undefined;
  max?: number;
  tone?: "teal" | "amber" | "red" | "blue" | "slate";
  height?: string;
}) {
  const ratio = value === null || value === undefined ? 0 : Math.max(0, Math.min(1, value / max));
  const colors = {
    teal: "bg-teal-500",
    amber: "bg-signal-amber",
    red: "bg-signal-red",
    blue: "bg-signal-blue",
    slate: "bg-ink-300",
  }[tone];
  return (
    <div className={`w-full overflow-hidden rounded-full bg-ink-100 ${height}`}>
      <div className={`${height} rounded-full ${colors} transition-all`} style={{ width: `${ratio * 100}%` }} />
    </div>
  );
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = "max-w-2xl",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label="Detail panel">
      <button type="button" aria-label="Close panel" className="absolute inset-0 bg-navy-950/40 backdrop-blur-[2px]" onClick={onClose} />
      <div className={`relative flex h-full w-full ${width} animate-fade-in flex-col bg-white shadow-float`}>
        <header className="flex items-start justify-between gap-4 border-b border-ink-300/60 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-ink-900">{title}</h2>
            {subtitle && <div className="mt-0.5 text-xs text-ink-500">{subtitle}</div>}
          </div>
          <button type="button" className="rounded-lg p-2 text-ink-500 hover:bg-ink-100" onClick={onClose} aria-label="Close">
            <IconClose className="h-5 w-5" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
        {footer && <footer className="border-t border-ink-300/60 px-5 py-4">{footer}</footer>}
      </div>
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <button type="button" aria-label="Close dialog" className="absolute inset-0 bg-navy-950/50 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative w-full max-w-lg animate-fade-in rounded-2xl bg-white p-6 shadow-float">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-ink-900">{title}</h2>
            {subtitle && <p className="mt-1 text-xs leading-5 text-ink-500">{subtitle}</p>}
          </div>
          <button type="button" className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100" onClick={onClose} aria-label="Close">
            <IconClose className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink-900">{children}</dd>
    </div>
  );
}

export function Spinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden="true" />
  );
}
