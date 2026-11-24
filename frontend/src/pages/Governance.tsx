import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { IconAlert, IconCheck, IconDatabase, IconGovernance, IconInfo, IconRefresh } from "../components/Icons";
import {
  Badge,
  Callout,
  Card,
  EmptyBlock,
  ErrorBlock,
  KeyValue,
  LoadingBlock,
  MeterBar,
  PageHeader,
  StatCard,
  StatusBadge,
} from "../components/ui";
import { useApi } from "../lib/useApi";
import type { GovernanceResponse } from "../lib/types";
import { formatDateTime, formatNumber, formatPercent, titleCase } from "../lib/format";

const PRIORITY_COLORS: Record<string, string> = {
  P1: "#dc2626",
  P2: "#f59e0b",
  P3: "#2563eb",
  P4: "#06b6d4",
  P5: "#cbd5e1",
};

const DATASET_LABELS: Record<string, string> = {
  assets: "Assets",
  transformers: "Transformers",
  substations: "Substations",
  circuit_breakers: "Circuit breakers",
  feeders: "Feeders",
  telemetry: "Telemetry readings",
  work_orders: "Maintenance work orders",
  inspections: "Inspections",
  failures: "Failure incidents",
  weather: "Weather observations",
  risk_records: "Derived risk records",
  knowledge_documents: "Knowledge documents",
  knowledge_chunks: "Knowledge chunks",
  engineering_decisions: "Engineering decisions",
  decision_events: "Decision audit events",
  data_quality_results: "Data-quality results",
};

export default function Governance() {
  const { data, loading, error, reload } = useApi<GovernanceResponse>("/api/v1/governance");

  if (loading && !data) {
    return (
      <>
        <PageHeader eyebrow="Trust & lineage" title="Governance and Audit" description="Loading lineage, quality, and audit records…" />
        <div className="grid gap-4 lg:grid-cols-2">
          <LoadingBlock rows={7} />
          <LoadingBlock rows={7} />
        </div>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <PageHeader eyebrow="Trust & lineage" title="Governance and Audit" />
        <ErrorBlock message={error ?? "No governance data was returned."} onRetry={reload} />
      </>
    );
  }

  const priorityData = ["P1", "P2", "P3", "P4", "P5"].map((priority) => ({
    name: priority,
    value: data.risk_generation.by_priority[priority] ?? 0,
  }));
  const severityTotal = Object.values(data.data_quality.by_severity).reduce((sum, value) => sum + value, 0);
  const datasetRows = Object.entries(data.datasets).filter(([, value]) => value > 0);
  const failedPercent =
    data.data_quality.records_checked > 0
      ? data.data_quality.records_failed / data.data_quality.records_checked
      : 0;
  const corpusRows = Object.entries(data.datasets).filter(([key]) => key.startsWith("knowledge_"));

  return (
    <>
      <PageHeader
        eyebrow="Trust & lineage"
        title="Governance and Audit"
        description="Trace what is in the warehouse, how each dataset arrived, which model produced each risk record, and exactly who changed each engineering decision. Every number below is read directly from PostgreSQL."
        actions={
          <>
            <Badge tone="amber">Synthetic demonstration</Badge>
            <button className="btn-ghost" type="button" onClick={reload}>
              <IconRefresh className="h-4 w-4" /> Refresh
            </button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Asset dimension"
          value={formatNumber(data.datasets.assets)}
          hint={`${formatNumber(data.datasets.telemetry)} telemetry rows`}
          icon={<IconDatabase className="h-5 w-5" />}
        />
        <StatCard
          label="Derived risk records"
          value={formatNumber(data.risk_generation.records)}
          hint={`${data.risk_generation.model_versions.length} model version(s) · ${data.risk_generation.prediction_cutoffs.length} cutoff(s)`}
          tone="blue"
          icon={<IconGovernance className="h-5 w-5" />}
        />
        <StatCard
          label="Data-quality failures"
          value={formatNumber(data.data_quality.records_failed)}
          hint={`${formatPercent(failedPercent, 1)} of ${formatNumber(data.data_quality.records_checked)} checked records`}
          tone="amber"
          icon={<IconAlert className="h-5 w-5" />}
        />
        <StatCard
          label="Audit events"
          value={formatNumber(data.datasets.decision_events)}
          hint={`${formatNumber(data.datasets.engineering_decisions)} human decision records`}
          tone="green"
          icon={<IconCheck className="h-5 w-5" />}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Card title="Warehouse inventory" subtitle="Row counts by dataset, read live from PostgreSQL" bodyClassName="p-0">
          <div className="max-h-[420px] overflow-y-auto">
            <table className="w-full">
              <thead className="table-head sticky top-0">
                <tr>
                  <th className="px-5 py-2.5">Dataset</th>
                  <th className="px-5 py-2.5 text-right">Rows</th>
                </tr>
              </thead>
              <tbody>
                {datasetRows.map(([key, value]) => (
                  <tr key={key} className="table-row">
                    <td className="table-cell py-2.5">{DATASET_LABELS[key] ?? titleCase(key)}</td>
                    <td className="table-cell py-2.5 text-right font-mono text-xs font-semibold text-ink-900">{formatNumber(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Database and migration state" subtitle="Runtime metadata" bodyClassName="p-5">
            <dl className="grid grid-cols-2 gap-4">
              <KeyValue label="Alembic revision"><span className="font-mono text-xs">{data.database.alembic_revision ?? "unknown"}</span></KeyValue>
              <KeyValue label="Engine">{data.database.engine}</KeyValue>
              <KeyValue label="Environment">Synthetic demonstration</KeyValue>
              <KeyValue label="Risk cutoffs">
                {data.risk_generation.prediction_cutoffs.length === 0
                  ? "—"
                  : formatDateTime(data.risk_generation.prediction_cutoffs[0])}
              </KeyValue>
            </dl>
            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-ink-500">Records failing a quality check</span>
                <span className="font-semibold text-ink-700">{formatPercent(failedPercent, 2)}</span>
              </div>
              <MeterBar value={failedPercent} max={1} tone={failedPercent > 0.05 ? "amber" : "teal"} />
            </div>
          </Card>

          <Card title="Risk generation lineage" subtitle="Which model produced the current risk workspace" bodyClassName="p-5">
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={priorityData} margin={{ top: 4, right: 8, bottom: 0, left: -22 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e7ec" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                  <Tooltip
                    formatter={(value: number) => [formatNumber(value), "Assets"]}
                    contentStyle={{ borderRadius: 12, borderColor: "#e4e7ec", fontSize: 12 }}
                  />
                  <Bar dataKey="value" radius={[5, 5, 0, 0]} barSize={30}>
                    {priorityData.map((entry) => (
                      <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {data.risk_generation.model_versions.length === 0 ? (
                <Badge tone="red">No model version recorded</Badge>
              ) : (
                data.risk_generation.model_versions.map((version) => (
                  <Badge key={version} tone="slate">
                    <span className="font-mono">{version}</span>
                  </Badge>
                ))
              )}
            </div>
            <p className="mt-2 text-[11px] leading-5 text-ink-500">
              {formatNumber(data.risk_generation.data_quality_warning_count)} risk records carry at least one data-quality warning.
            </p>
          </Card>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card title="Pipeline ingestion runs" subtitle="Most recent operational data loads" bodyClassName="p-0">
          {data.ingestion_runs.length === 0 ? (
            <div className="p-5"><EmptyBlock title="No ingestion runs recorded" /></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px]">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Source</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Read</th>
                    <th className="px-4 py-3 text-right">Inserted</th>
                    <th className="px-4 py-3 text-right">Updated</th>
                    <th className="px-4 py-3 text-right">Rejected</th>
                    <th className="px-5 py-3">Started</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ingestion_runs.map((run) => (
                    <tr key={run.run_id} className="table-row">
                      <td className="table-cell">
                        <p className="font-medium text-ink-900">{run.source_name}</p>
                        <p className="font-mono text-[10px] text-ink-500">{run.run_id.slice(0, 8)}</p>
                      </td>
                      <td className="table-cell"><StatusBadge status={run.status} /></td>
                      <td className="table-cell text-right font-mono text-xs">{formatNumber(run.rows_read)}</td>
                      <td className="table-cell text-right font-mono text-xs">{formatNumber(run.rows_inserted)}</td>
                      <td className="table-cell text-right font-mono text-xs">{formatNumber(run.rows_updated)}</td>
                      <td className={`table-cell text-right font-mono text-xs ${run.rows_rejected > 0 ? "text-signal-red" : ""}`}>
                        {formatNumber(run.rows_rejected)}
                      </td>
                      <td className="table-cell text-xs text-ink-500">{formatDateTime(run.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Data-quality posture" subtitle="Checks executed by the pipeline" bodyClassName="p-5">
          <div className="grid grid-cols-2 gap-4">
            <KeyValue label="Checks">{formatNumber(data.data_quality.checks)}</KeyValue>
            <KeyValue label="Records checked">{formatNumber(data.data_quality.records_checked)}</KeyValue>
            <KeyValue label="Records failed">{formatNumber(data.data_quality.records_failed)}</KeyValue>
            <KeyValue label="Severity buckets">{Object.keys(data.data_quality.by_severity).length}</KeyValue>
          </div>
          <div className="mt-4 space-y-2">
            {Object.entries(data.data_quality.by_severity).map(([severity, count]) => (
              <div key={severity} className="flex items-center justify-between text-xs">
                <StatusBadge status={severity.toUpperCase()} />
                <span className="font-semibold text-ink-700">{formatNumber(count)} checks</span>
              </div>
            ))}
            {severityTotal === 0 && <p className="text-xs text-ink-500">No severity data recorded.</p>}
          </div>
          <p className="mt-4 text-[11px] leading-5 text-ink-500">
            Quality results describe synthetic source coverage and format checks. They are not a certification of fitness for operational use.
          </p>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Card title="Quality checks with failures" subtitle="Largest contributors first" bodyClassName="p-0">
          {data.data_quality.checks_with_failures.length === 0 ? (
            <div className="p-5"><EmptyBlock title="No failing quality checks" /></div>
          ) : (
            <div className="max-h-[360px] overflow-y-auto">
              <table className="w-full">
                <thead className="table-head sticky top-0">
                  <tr>
                    <th className="px-5 py-2.5">Dataset / check</th>
                    <th className="px-3 py-2.5">Severity</th>
                    <th className="px-5 py-2.5 text-right">Failed</th>
                  </tr>
                </thead>
                <tbody>
                  {data.data_quality.checks_with_failures.map((check) => (
                    <tr key={check.result_id ?? `${check.dataset}-${check.check}`} className="table-row">
                      <td className="table-cell">
                        <p className="text-xs font-semibold text-ink-900">{titleCase(check.check)}</p>
                        <p className="text-[10px] text-ink-500">{check.dataset}</p>
                        {check.details ? <p className="mt-0.5 text-[10px] leading-4 text-ink-500">{check.details}</p> : null}
                      </td>
                      <td className="px-3 py-3"><StatusBadge status={check.severity.toUpperCase()} /></td>
                      <td className="px-5 py-3 text-right font-mono text-xs font-semibold text-ink-900">{formatNumber(check.records_failed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Knowledge corpus governance" subtitle="Documents, chunks, and ingestion history" bodyClassName="p-5">
          <div className="grid grid-cols-2 gap-4">
            {corpusRows.length === 0 ? (
              <p className="text-xs text-ink-500">No corpus counts recorded.</p>
            ) : (
              corpusRows.map(([key, value]) => (
                <KeyValue key={key} label={DATASET_LABELS[key] ?? titleCase(key)}>{formatNumber(value)}</KeyValue>
              ))
            )}
          </div>
          <div className="mt-4">
            <p className="label">Categories</p>
            <div className="flex flex-wrap gap-1.5">
              {data.knowledge.categories.map((item) => (
                <Badge key={item.category} tone="slate">{item.category} · {item.count}</Badge>
              ))}
            </div>
          </div>
          <div className="mt-4">
            <p className="label">Latest knowledge ingestion</p>
            {data.knowledge.ingestion_runs.length === 0 ? (
              <p className="text-xs text-ink-500">No run recorded.</p>
            ) : (
              <ul className="space-y-2">
                {data.knowledge.ingestion_runs.slice(0, 3).map((run) => (
                  <li key={run.run_id} className="flex items-center justify-between gap-2 rounded-lg bg-ink-50 px-3 py-2 text-[11px]">
                    <span className="text-ink-500">{formatDateTime(run.started_at)}</span>
                    <span className="font-medium text-ink-700">{run.documents_processed} docs · {run.chunks_created} chunks · {run.error_count} errors</span>
                    <StatusBadge status={run.status} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Card title="Model registry" subtitle="Persisted artifacts and their recorded evaluation" bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3">Model</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3 text-right">Threshold</th>
                  <th className="px-3 py-3 text-right">Val ROC AUC</th>
                  <th className="px-3 py-3 text-right">Test F1</th>
                  <th className="px-5 py-3 text-right">Version</th>
                </tr>
              </thead>
              <tbody>
                {data.models.map((model) => (
                  <tr key={model.model_name} className="table-row">
                    <td className="table-cell">
                      <p className="font-semibold text-ink-900">{model.label}</p>
                      <p className="text-[10px] text-ink-500">{model.model_name}</p>
                    </td>
                    <td className="px-3 py-3"><Badge tone={model.available ? "green" : "red"}>{model.available ? "Ready" : "Missing"}</Badge></td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{model.threshold ?? "—"}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{model.validation_metrics?.roc_auc?.toFixed(3) ?? "—"}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs">{model.test_metrics?.f1?.toFixed(3) ?? "—"}</td>
                    <td className="px-5 py-3 text-right font-mono text-[10px] text-ink-500">{model.model_version ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-ink-300/50 px-5 py-3">
            <Callout tone="amber">{data.model_warning}</Callout>
          </div>
        </Card>

        <Card title="Decision audit trail" subtitle="Most recent transitions, newest first" bodyClassName="p-0">
          {data.decisions.audit_events.length === 0 ? (
            <div className="p-5"><EmptyBlock title="No decision events recorded" /></div>
          ) : (
            <ol className="max-h-[420px] divide-y divide-ink-300/50 overflow-y-auto">
              {data.decisions.audit_events.map((event) => (
                <li key={event.event_id} className="px-5 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-ink-900">{titleCase(event.action)}</p>
                    <StatusBadge status={event.new_status} />
                  </div>
                  <p className="font-mono text-[10px] text-ink-500">{event.decision_id.slice(0, 8)}</p>
                  <p className="mt-0.5 text-[11px] text-ink-500">{event.reviewer} · {formatDateTime(event.timestamp)}</p>
                  {event.reason && <p className="mt-1 text-[11px] leading-5 text-ink-600">{event.reason}</p>}
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Recent decisions" bodyClassName="p-0">
          {data.decisions.recent.length === 0 ? (
            <div className="p-5"><EmptyBlock title="No decisions recorded" /></div>
          ) : (
            <ul className="divide-y divide-ink-300/50">
              {data.decisions.recent.map((decision) => (
                <li key={decision.decision_id} className="flex items-center justify-between gap-3 px-5 py-3">
                  <div>
                    <p className="text-xs font-semibold text-ink-900">{decision.asset_id} · {titleCase(decision.asset_type)}</p>
                    <p className="text-[10px] text-ink-500">
                      {decision.reviewer} · {formatDateTime(decision.updated_at)}
                      {decision.risk_category ? ` · ${titleCase(decision.risk_category)}` : ""}
                    </p>
                  </div>
                  <StatusBadge status={decision.decision_status} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Declared limitations" subtitle="What this platform does not claim" bodyClassName="p-5">
          <ul className="space-y-2 text-xs leading-5 text-ink-600">
            {data.limitations.map((limitation) => (
              <li key={limitation} className="flex gap-2">
                <IconInfo className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />
                {limitation}
              </li>
            ))}
          </ul>
          <div className="mt-4 rounded-xl bg-ink-50 px-4 py-3 text-[11px] leading-5 text-ink-500">
            <p className="flex gap-2">
              <IconInfo className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />
              This page reports database state; it is not a compliance certification or an audit opinion.
            </p>
          </div>
        </Card>
      </div>
    </>
  );
}
