export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Asset {
  asset_id: string;
  name: string;
  asset_type: string;
  status: string;
  region: string | null;
  install_date: string | null;
  operating_hours_cumulative: number | null;
}

export interface AssetFilterOption {
  value: string;
  label: string;
  count: number;
}

export interface AssetFilters {
  asset_types: AssetFilterOption[];
  statuses: AssetFilterOption[];
  regions: AssetFilterOption[];
}

export interface AssetSummary {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
}

export interface AssetProfile {
  asset: Asset & {
    transformer_detail?: Record<string, unknown> | null;
    substation_detail?: Record<string, unknown> | null;
    circuit_breaker_detail?: Record<string, unknown> | null;
    feeder_detail?: Record<string, unknown> | null;
  };
  risk: RiskItem | null;
  telemetry: {
    count: number;
    latest: {
      timestamp: string;
      temperature_c: number | null;
      load_pct: number | null;
      voltage_kv: number | null;
      current_a: number | null;
      vibration_mm_s: number | null;
    } | null;
  };
  recent_failures: {
    failure_id: string;
    failure_category: string;
    failure_timestamp: string;
    failure_severity: number;
    downtime_hours: number;
  }[];
  recent_work_orders: {
    work_order_id: string;
    work_type: string;
    priority: string;
    status: string;
    opened_at: string;
    completed_at: string | null;
  }[];
  recent_inspections: {
    inspection_id: string;
    inspection_date: string;
    condition: string;
    severity: number;
    findings: string;
  }[];
}

export interface Criticality {
  tier: "low" | "medium" | "high" | "critical";
  label: string;
  score: number;
  reasons: string[];
}

export interface RiskItem {
  rank: number;
  asset_id: string;
  asset_type: string;
  asset_name: string | null;
  region: string | null;
  status: string | null;
  prediction_cutoff: string;
  risk_category: string;
  model_probability: number | null;
  model_probability_percentile: number | null;
  anomaly_score: number | null;
  anomaly_percentile: number | null;
  criticality: Criticality;
  data_quality: Record<string, unknown>;
  data_quality_flags: string[];
  primary_drivers: string[];
  model_version: string | null;
  limitations: string[];
  review_priority: string;
  review_priority_label: string;
  decision_count: number;
  latest_decision_status: string | null;
  latest_decision_id: string | null;
}

export interface RiskSummary {
  total: number;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
  by_category: Record<string, number>;
  criticality: Record<string, number>;
  probability_buckets: Record<string, number>;
  data_quality_warning_count: number;
  model_versions: string[];
  prediction_cutoffs: string[];
  priority_rules: string[];
  top_assets: RiskItem[];
  filter_options?: {
    asset_types: string[];
    priorities: string[];
    risk_categories: string[];
  };
}

export interface RiskListResponse {
  items: RiskItem[];
  total: number;
  limit: number;
  offset: number;
  summary: RiskSummary;
  filter_options: NonNullable<RiskSummary["filter_options"]>;
}

export interface ExplanationDeviation {
  feature: string;
  label: string;
  value: number;
  baseline: number;
  robust_z: number;
  direction: "above" | "below";
}

export interface Explanation {
  asset_id: string;
  unavailable?: boolean;
  reason?: string;
  asset_type?: string;
  asset_name?: string;
  region?: string | null;
  status?: string;
  prediction_cutoff?: string;
  model_name?: string;
  model_version?: string;
  model_threshold?: number;
  probability?: number;
  risk_category?: string;
  anomaly_score?: number | null;
  criticality?: Criticality;
  top_deviations?: ExplanationDeviation[];
  all_deviation_count?: number;
  global_importance?: { feature: string; label: string; importance: number }[];
  data_quality?: Record<string, unknown>;
  warnings?: string[];
  missing_features?: string[];
  methodology?: Record<string, string>;
  baseline_created_at?: string;
  baseline_artifact?: string;
  z_cap?: number;
}

export interface Metrics {
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  brier?: number;
  roc_auc?: number;
  average_precision?: number;
  prevalence?: number;
  confusion_matrix?: {
    true_negative: number;
    false_positive: number;
    true_positive: number;
    false_negative: number;
  };
}

export interface ModelSummary {
  model_name: string;
  label: string;
  available: boolean;
  model_version: string | null;
  artifact_path: string;
  artifact_size_bytes: number | null;
  artifact_modified_at: string | null;
  metadata_path: string;
  threshold: number | null;
  feature_count: number;
  positive_count: number | null;
  negative_count: number | null;
  split: {
    train_assets?: number;
    validation_assets?: number;
    test_assets?: number;
  };
  validation_metrics: Metrics | null;
  test_metrics: Metrics | null;
  metric_explanations: Record<string, string>;
  evaluation_context: string;
  artifact_persistence: string;
}

export interface PredictiveResponse {
  available: boolean;
  preferred_model: ModelSummary | null;
  models: ModelSummary[];
  comparison: Record<string, unknown> | null;
  comparison_available: boolean;
  message: string | null;
  evaluation_dataset: string;
  synthetic_warning: string;
}

export interface OverviewResponse {
  synthetic: boolean;
  assets: {
    total: number;
    by_type: Record<string, number>;
    by_status: Record<string, number>;
    by_region: { region: string; count: number }[];
  };
  failures: {
    total: number;
    last_90_days: number;
    window_end: string | null;
    severity: { severity: number; count: number }[];
  };
  work_orders: {
    by_status: Record<string, number>;
    active_by_priority: Record<string, number>;
    active_total: number;
    oldest_open_at: string | null;
  };
  inspections: {
    total: number;
    assets_inspected: number;
    coverage_percent: number;
    conditions: Record<string, number>;
    latest_inspection: string | null;
  };
  risks: RiskSummary;
  risk_record_count: number;
  knowledge: { documents: number; chunks: number };
  decisions: {
    total: number;
    by_status: Record<string, number>;
    active: number;
    recent: {
      decision_id: string;
      asset_id: string;
      asset_type: string;
      decision_status: string;
      reviewer: string;
      created_at: string;
    }[];
  };
  recent_ingestion: IngestionRun[];
  model: {
    available: boolean;
    name: string | null;
    model_name: string | null;
    model_version: string | null;
    threshold: number | null;
  };
  freshness: {
    latest_telemetry: string | null;
    latest_failure: string | null;
    latest_inspection: string | null;
    latest_weather: string | null;
  };
  top_risks: RiskItem[];
}

export interface IngestionRun {
  run_id: string;
  source_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  rows_read: number;
  rows_inserted: number;
  rows_updated: number;
  rows_skipped?: number;
  rows_rejected: number;
  error_summary?: string | null;
  report_path?: string | null;
}

export interface QualityCheck {
  result_id?: number;
  dataset: string;
  check: string;
  severity: string;
  records_failed: number;
  details: string;
}

export interface GovernanceResponse {
  synthetic: boolean;
  database: { alembic_revision: string | null; engine: string };
  datasets: Record<string, number>;
  ingestion_runs: IngestionRun[];
  data_quality: {
    checks: number;
    records_checked: number;
    records_failed: number;
    by_severity: Record<string, number>;
    checks_with_failures: QualityCheck[];
  };
  knowledge: {
    documents: number;
    chunks: number;
    categories: { category: string; count: number }[];
    ingestion_runs: {
      run_id: string;
      status: string;
      started_at: string;
      completed_at: string | null;
      documents_processed: number;
      chunks_created: number;
      error_count: number;
    }[];
  };
  models: ModelSummary[];
  model_warning: string;
  risk_generation: {
    records: number;
    by_priority: Record<string, number>;
    by_type: Record<string, number>;
    model_versions: string[];
    prediction_cutoffs: string[];
    data_quality_warning_count: number;
  };
  decisions: {
    recent: {
      decision_id: string;
      asset_id: string;
      asset_type: string;
      decision_status: string;
      reviewer: string;
      risk_category: string | null;
      model_version: string | null;
      created_at: string;
      updated_at: string;
      decided_at: string | null;
    }[];
    audit_events: {
      event_id: string;
      decision_id: string;
      previous_status: string | null;
      new_status: string;
      action: string;
      reviewer: string;
      reason: string | null;
      timestamp: string;
    }[];
  };
  limitations: string[];
}

export interface KnowledgeDocument {
  document_id: string;
  title: string;
  category: string;
  revision: string;
  source_filename: string;
  checksum: string;
  equipment_applicability: string | null;
  publication_date: string | null;
  mime_type: string | null;
  chunk_count: number;
}

export interface KnowledgeChunk {
  chunk_id: string;
  document_id: string;
  page_number: number | null;
  text: string;
  source_checksum: string;
  document_title: string | null;
  category: string | null;
  equipment: string | null;
}

export interface KnowledgeDocumentContent extends KnowledgeDocument {
  extracted_text: string;
  chunks: KnowledgeChunk[];
}

export interface KnowledgeStats {
  documents: number;
  chunks: number;
  categories: { category: string; documents: number }[];
  equipment: { equipment: string; documents: number }[];
  formats: { mime_type: string; documents: number }[];
  latest_ingestion: {
    run_id: string;
    status: string;
    started_at: string;
    completed_at: string | null;
    documents_processed: number;
    chunks_created: number;
    error_count: number;
  } | null;
  synthetic: boolean;
  limitations: string[];
}

export interface Citation {
  document_id: string | null;
  title: string | null;
  revision: string | null;
  page_number: number | null;
  chunk_id: string | null;
  source_checksum: string | null;
  excerpt: string | null;
}

export interface AskResponse {
  question: string;
  asset_id: string | null;
  answer: string;
  citations: Citation[];
  key_facts: string[];
  limitations: string[];
  evidence_sufficient: boolean;
  confidence: string;
  provider: string;
  route: "structured_database" | "document_retrieval";
  structured_data: {
    route: string;
    metric: string;
    value: number | string | null;
    text: string;
    breakdown: Record<string, unknown>;
  } | null;
}

export interface Decision {
  decision_id: string;
  asset_id: string;
  asset_type: string;
  model_version: string | null;
  predicted_risk_probability: number | null;
  risk_category: string | null;
  anomaly_score: number | null;
  decision_status: string;
  decision_reason: string | null;
  replacement_risk_category: string | null;
  reviewer: string;
  created_at: string;
  updated_at: string;
  decided_at: string | null;
}

export interface DecisionDetail {
  decision: Decision;
  asset: {
    asset_id: string;
    name: string;
    asset_type: string;
    status: string;
    region: string | null;
  } | null;
  current_risk: {
    risk_category: string;
    model_probability: number | null;
    anomaly_score: number | null;
    model_version: string | null;
    prediction_cutoff: string;
  } | null;
  history: {
    event_id: string;
    previous_status: string | null;
    new_status: string;
    action: string;
    reviewer: string;
    reason: string | null;
    timestamp: string;
  }[];
  evidence: {
    id: number;
    document_id: string;
    chunk_id: string;
    document_title: string;
    revision: string;
    page_number: number | null;
    excerpt: string;
    source_checksum: string;
  }[];
}
