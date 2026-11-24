/// <reference types="vitest/globals" />
import {
  formatBytes,
  formatDate,
  formatNumber,
  formatPercent,
  formatProbability,
  formatRelative,
  prettyFeature,
  statusTone,
  titleCase,
  truncate,
} from "./format";

test("formats numbers with an explicit missing value", () => {
  expect(formatNumber(2600)).toBe("2,600");
  expect(formatNumber(null)).toBe("—");
  expect(formatNumber(0)).toBe("0");
});

test("formats rates and probabilities without implying false precision", () => {
  expect(formatPercent(0.9234, 1)).toBe("92.3%");
  expect(formatPercent(null)).toBe("—");
  expect(formatProbability(0.9999)).toBe("1.000");
  expect(formatProbability(undefined)).toBe("—");
});

test("normalises labels and feature names", () => {
  expect(titleCase("circuit_breakers")).toBe("Circuit Breakers");
  expect(titleCase("PENDING_REVIEW")).toBe("PENDING REVIEW");
  expect(prettyFeature("telemetry_load_pct_trend_per_day")).toBe("Load pct trend per day");
  expect(prettyFeature(null)).toBe("—");
});

test("maps statuses to consistent semantic tones", () => {
  expect(statusTone("approved")).toBe("green");
  expect(statusTone("pending_review")).toBe("amber");
  expect(statusTone("escalated")).toBe("red");
  expect(statusTone("in_review")).toBe("blue");
  expect(statusTone("unknown")).toBe("slate");
});

test("formats timestamps, sizes, and truncation", () => {
  expect(formatDate("2026-01-02T10:00:00")).toContain("2026");
  expect(formatDate(null)).toBe("—");
  expect(formatRelative(new Date(Date.now() - 60_000).toISOString())).toMatch(/ago/);
  expect(formatBytes(2048)).toBe("2.0 KB");
  expect(truncate("abcdefghij", 5)).toBe("abcd…");
});
