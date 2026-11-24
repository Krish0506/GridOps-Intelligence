export function formatNumber(value: number | null | undefined, options?: Intl.NumberFormatOptions): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", options).format(value);
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatPercentValue(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function formatProbability(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(3);
}

export function formatScore(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "2-digit" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.round(diffMs / 60000);
  if (Math.abs(minutes) < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 48) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function prettyFeature(value: string | null | undefined): string {
  if (!value) return "—";
  const cleaned = value
    .replace(/^quality_/, "")
    .replace(/^telemetry_/, "")
    .replace(/_/g, " ")
    .trim();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

export function truncate(value: string, length: number): string {
  if (value.length <= length) return value;
  return `${value.slice(0, length - 1)}…`;
}

export function statusTone(status: string | null | undefined): "green" | "amber" | "red" | "blue" | "slate" | "teal" {
  const normalized = (status ?? "").toUpperCase();
  if (["APPROVED", "COMPLETED", "ACTIVE", "INGESTED", "OK", "PASSED"].includes(normalized)) return "green";
  if (["PENDING_REVIEW", "DEFERRED", "IN_PROGRESS", "RUNNING", "SPARSE"].includes(normalized)) return "amber";
  if (["REJECTED", "ESCALATED", "FAILED", "CRITICAL", "RETIRED"].includes(normalized)) return "red";
  if (["IN_REVIEW", "OVERRIDDEN"].includes(normalized)) return "blue";
  return "slate";
}

export function priorityTone(priority: string): "red" | "amber" | "blue" | "teal" | "slate" {
  switch (priority) {
    case "P1":
      return "red";
    case "P2":
      return "amber";
    case "P3":
      return "blue";
    case "P4":
      return "teal";
    default:
      return "slate";
  }
}

export function criticalityTone(tier: string): "red" | "amber" | "blue" | "slate" {
  switch (tier) {
    case "critical":
      return "red";
    case "high":
      return "amber";
    case "medium":
      return "blue";
    default:
      return "slate";
  }
}
