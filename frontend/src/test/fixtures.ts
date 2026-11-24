import { vi } from "vitest";

export interface MockRoute {
  match: (url: string, init?: RequestInit) => boolean;
  response: unknown | (() => unknown);
  status?: number;
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Install a deterministic fetch implementation for a component test.
 * Routes are evaluated in order, so put specific paths before wildcards.
 */
export function mockFetch(routes: MockRoute[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    for (const route of routes) {
      if (route.match(url, init)) {
        const body =
          typeof route.response === "function"
            ? (route.response as () => unknown)()
            : route.response;
        return jsonResponse(body, route.status ?? 200);
      }
    }
    return jsonResponse({ detail: `Unmatched request: ${init?.method ?? "GET"} ${url}` }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const overviewFixture = {
  synthetic: true,
  assets: {
    total: 2600,
    by_type: { transformers: 1200, substations: 300, circuit_breakers: 800, feeders: 300 },
    by_status: { active: 2500, retired: 100 },
    by_region: [{ region: "North", count: 500 }],
  },
  failures: {
    total: 60,
    last_90_days: 12,
    window_end: "2026-01-01T00:00:00",
    severity: [
      { severity: 2, count: 30 },
      { severity: 4, count: 10 },
    ],
  },
  work_orders: {
    by_status: { open: 20, completed: 1508 },
    active_by_priority: { critical: 5, high: 10 },
    active_total: 40,
    oldest_open_at: "2025-12-01T00:00:00",
  },
  inspections: {
    total: 2584,
    assets_inspected: 1800,
    coverage_percent: 69.2,
    conditions: { good: 1000 },
    latest_inspection: "2026-01-02T00:00:00",
  },
  risks: {
    total: 2600,
    by_priority: { P1: 9, P2: 121, P3: 646, P4: 875, P5: 949 },
    by_type: { transformers: 1200 },
    by_category: { predicted_failure: 1248, predicted_no_failure: 1352 },
    criticality: { low: 91, medium: 2073, high: 383, critical: 53 },
    probability_buckets: { "0-0.05": 235, "0.9-1.0": 801 },
    data_quality_warning_count: 2436,
    model_versions: ["logistic_regression@abc123"],
    prediction_cutoffs: ["2026-01-02T00:00:00"],
    priority_rules: ["P1 requires a top percentile and high consequence."],
    top_assets: [],
  },
  risk_record_count: 2600,
  knowledge: { documents: 36, chunks: 36 },
  decisions: {
    total: 2,
    by_status: { PENDING_REVIEW: 1, APPROVED: 1 },
    active: 1,
    recent: [],
  },
  recent_ingestion: [],
  model: {
    available: true,
    name: "Logistic regression",
    model_name: "logistic_regression",
    model_version: "logistic_regression@abc123",
    threshold: 0.5,
  },
  freshness: {
    latest_telemetry: "2026-01-02T00:00:00",
    latest_failure: "2026-01-01T00:00:00",
    latest_inspection: "2026-01-02T00:00:00",
    latest_weather: "2026-01-02T00:00:00",
  },
  top_risks: [
    {
      rank: 1,
      asset_id: "CB-00348",
      asset_type: "circuit_breakers",
      asset_name: "Breaker 348",
      region: "North",
      status: "active",
      prediction_cutoff: "2026-01-02T00:00:00",
      risk_category: "predicted_failure",
      model_probability: 1,
      model_probability_percentile: 1,
      anomaly_score: 50,
      anomaly_percentile: 1,
      criticality: { tier: "medium", label: "Medium", score: 2, reasons: [] },
      data_quality: {},
      data_quality_flags: [],
      primary_drivers: ["telemetry_load_pct_trend_per_day"],
      model_version: "logistic_regression@abc123",
      limitations: [],
      review_priority: "P1",
      review_priority_label: "Immediate review",
      decision_count: 0,
      latest_decision_status: null,
      latest_decision_id: null,
    },
  ],
};

const riskItemFixture = {
  ...overviewFixture.top_risks[0],
  asset_id: "CB-00001",
  asset_name: "Breaker 1",
  rank: 1,
};

export const riskListFixture = {
  items: [riskItemFixture],
  total: 1,
  limit: 25,
  offset: 0,
  summary: {
    ...overviewFixture.risks,
    total: 1,
    by_priority: { P1: 1, P2: 0, P3: 0, P4: 0, P5: 0 },
    by_category: { predicted_failure: 1 },
    filter_options: {
      asset_types: ["circuit_breakers"],
      priorities: ["P1", "P2", "P3", "P4", "P5"],
      risk_categories: ["predicted_failure", "predicted_no_failure"],
    },
  },
  filter_options: {
    asset_types: ["circuit_breakers"],
    priorities: ["P1", "P2", "P3", "P4", "P5"],
    risk_categories: ["predicted_failure", "predicted_no_failure"],
  },
};

export const riskDetailFixture = {
  item: riskItemFixture,
  explanation: {
    asset_id: "CB-00001",
    unavailable: false,
    asset_type: "circuit_breakers",
    asset_name: "Breaker 1",
    prediction_cutoff: "2026-01-02T00:00:00",
    model_name: "logistic_regression",
    model_version: "logistic_regression@abc123",
    model_threshold: 0.5,
    probability: 1,
    risk_category: "predicted_failure",
    anomaly_score: 50,
    criticality: { tier: "medium", label: "Medium", score: 2, reasons: ["Feeder dependency recorded."] },
    top_deviations: [
      {
        feature: "telemetry_load_pct_trend_per_day",
        label: "Load trend per day",
        value: 4.2,
        baseline: 0.1,
        robust_z: 18.4,
        direction: "above",
      },
    ],
    all_deviation_count: 12,
    global_importance: [],
    data_quality: { telemetry_coverage_ratio: 0.9, missing_value_ratio: 0.1, history_group_count: 2 },
    warnings: [],
    missing_features: [],
    methodology: { deviation: "Robust z-scores against the persisted population baseline." },
    baseline_created_at: "2026-01-02T00:00:00",
    baseline_artifact: "ml/artifacts/explainability/baseline.json",
    z_cap: 50,
  },
};

export const decisionFixture = {
  decision_id: "11111111-2222-3333-4444-555555555555",
  asset_id: "CB-00001",
  asset_type: "circuit_breakers",
  model_version: "logistic_regression@abc123",
  predicted_risk_probability: 0.99,
  risk_category: "predicted_failure",
  anomaly_score: 40,
  decision_status: "PENDING_REVIEW",
  decision_reason: "Review the load trend and inspection record.",
  replacement_risk_category: null,
  reviewer: "demo-reviewer",
  created_at: "2026-01-02T10:00:00",
  updated_at: "2026-01-02T10:00:00",
  decided_at: null,
};

export const decisionDetailFixture = {
  decision: decisionFixture,
  asset: {
    asset_id: "CB-00001",
    name: "Breaker 1",
    asset_type: "circuit_breakers",
    status: "active",
    region: "North",
  },
  current_risk: {
    risk_category: "predicted_failure",
    model_probability: 0.99,
    anomaly_score: 40,
    model_version: "logistic_regression@abc123",
    prediction_cutoff: "2026-01-02T00:00:00",
  },
  history: [
    {
      event_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      previous_status: null,
      new_status: "PENDING_REVIEW",
      action: "CREATE",
      reviewer: "demo-reviewer",
      reason: "Review the load trend and inspection record.",
      timestamp: "2026-01-02T10:00:00",
    },
  ],
  evidence: [],
};
