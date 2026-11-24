import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { IconAlert, IconAsset, IconChart, IconDatabase, IconDecision, IconPulse, IconRisk } from "../components/Icons";
import {
  Badge,
  Callout,
  Card,
  ErrorBlock,
  KeyValue,
  LoadingBlock,
  PageHeader,
  PriorityBadge,
  StatCard,
  StatusBadge,
} from "../components/ui";
import { useApi } from "../lib/useApi";
import type { OverviewResponse } from "../lib/types";
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatProbability,
  titleCase,
} from "../lib/format";

const PRIORITY_COLORS: Record<string, string> = {
  P1: "#dc2626",
  P2: "#f59e0b",
  P3: "#2563eb",
  P4: "#06b6d4",
  P5: "#cbd5e1",
};

const TYPE_COLORS = ["#0891b2", "#2563eb", "#f59e0b", "#64748b"];

export default function Overview() {
  const { data, loading, error, reload } = useApi<OverviewResponse>("/api/v1/overview");

  if (loading && !data) {
    return (
      <>
        <PageHeader eyebrow="Command center" title="Operations Overview" description="Loading the current synthetic operational picture…" />
        <div className="grid gap-4 lg:grid-cols-3">
          <LoadingBlock />
          <LoadingBlock />
          <LoadingBlock />
        </div>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <PageHeader eyebrow="Command center" title="Operations Overview" />
        <ErrorBlock message={error ?? "No overview data was returned."} onRetry={reload} />
      </>
    );
  }

  const typeData = Object.entries(data.assets.by_type).map(([name, value]) => ({
    name: titleCase(name),
    value,
  }));
  const priorityData = ["P1", "P2", "P3", "P4", "P5"].map((priority) => ({
    name: priority,
    value: data.risks.by_priority[priority] ?? 0,
  }));
  const severityData = data.failures.severity.map((entry) => ({
    name: `Sev ${entry.severity}`,
    value: entry.count,
  }));

  return (
    <>
      <PageHeader
        eyebrow="Command center"
        title="Operations Overview"
        description={
          <>
            A live view of the synthetic utility estate: asset health, maintenance pressure, predictive risk, evidence, and human review.
            Snapshot cutoff <span className="font-medium text-ink-700">{formatDateTime(data.risks.prediction_cutoffs[0])}</span>.
          </>
        }
        actions={
          <>
            <Badge tone="teal">Synthetic data</Badge>
            <Badge tone="slate">Read-only analytics</Badge>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Assets under management"
          value={formatNumber(data.assets.total)}
          hint={`${formatNumber(data.assets.by_status.active ?? 0)} active · ${formatNumber(data.assets.by_status.retired ?? 0)} retired`}
          icon={<IconAsset className="h-5 w-5" />}
        />
        <StatCard
          label="Active work orders"
          value={formatNumber(data.work_orders.active_total)}
          hint={`${formatNumber(data.work_orders.active_by_priority.critical ?? 0)} critical priority · ${formatNumber(data.work_orders.active_by_priority.high ?? 0)} high`}
          icon={<IconChart className="h-5 w-5" />}
          tone="amber"
        />
        <StatCard
          label="Failures · last 90 days"
          value={formatNumber(data.failures.last_90_days)}
          hint={`${formatNumber(data.failures.total)} incidents in synthetic history`}
          icon={<IconAlert className="h-5 w-5" />}
          tone="red"
        />
        <StatCard
          label="Decisions awaiting review"
          value={formatNumber(data.decisions.active)}
          hint={`${formatNumber(data.decisions.total)} decision records · no auto-approval`}
          icon={<IconDecision className="h-5 w-5" />}
          tone="blue"
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card
          title="Asset portfolio"
          subtitle="Inventory composition by equipment type"
          className="xl:col-span-1"
          bodyClassName="p-4"
        >
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={typeData} layout="vertical" margin={{ left: 8, right: 12, top: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e4e7ec" />
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: "#f8fafc" }}
                  formatter={(value: number) => [formatNumber(value), "Assets"]}
                  contentStyle={{ borderRadius: 12, borderColor: "#e4e7ec", fontSize: 12 }}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={18}>
                  {typeData.map((entry, index) => (
                    <Cell key={entry.name} fill={TYPE_COLORS[index % TYPE_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 space-y-2">
            {typeData.map((entry, index) => (
              <div key={entry.name} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-ink-500">
                  <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: TYPE_COLORS[index % TYPE_COLORS.length] }} />
                  {entry.name}
                </span>
                <span className="font-semibold text-ink-700">{formatNumber(entry.value)}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Risk review bands" subtitle={`Transparent triage over ${formatNumber(data.risk_record_count)} persisted risk records`} bodyClassName="p-4">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={priorityData} margin={{ left: -20, right: 8, top: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e7ec" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: "#f8fafc" }}
                  formatter={(value: number) => [formatNumber(value), "Assets"]}
                  contentStyle={{ borderRadius: 12, borderColor: "#e4e7ec", fontSize: 12 }}
                />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={34}>
                  {priorityData.map((entry) => (
                    <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge tone="red">P1 · {data.risks.by_priority.P1 ?? 0}</Badge>
            <Badge tone="amber">P2 · {data.risks.by_priority.P2 ?? 0}</Badge>
            <Badge tone="blue">P3 · {data.risks.by_priority.P3 ?? 0}</Badge>
            <Badge tone="teal">P4 · {data.risks.by_priority.P4 ?? 0}</Badge>
            <Badge tone="slate">P5 · {data.risks.by_priority.P5 ?? 0}</Badge>
          </div>
          <Link className="mt-3 inline-flex text-xs font-semibold text-teal-700 hover:text-teal-800" to="/risk">
            Open risk workbench →
          </Link>
        </Card>

        <Card title="Model in service" subtitle="Persisted artifact used for risk generation" bodyClassName="p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-lg font-semibold text-ink-900">{data.model.name ?? "Model unavailable"}</p>
              <p className="mt-0.5 font-mono text-[11px] text-ink-500">{data.model.model_version ?? "—"}</p>
            </div>
            <Badge tone={data.model.available ? "green" : "red"}>{data.model.available ? "Loaded" : "Missing"}</Badge>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-4">
            <KeyValue label="Decision threshold">{data.model.threshold ?? "—"}</KeyValue>
            <KeyValue label="Risk records">{formatNumber(data.risk_record_count)}</KeyValue>
            <KeyValue label="Model versions">{data.risks.model_versions.length}</KeyValue>
            <KeyValue label="Data-quality flags">{formatNumber(data.risks.data_quality_warning_count)}</KeyValue>
          </dl>
          <Callout tone="amber" title="Interpretation" >
            Model probability is a synthetic classifier output. The anomaly score is an unsupervised deviation magnitude, not a failure probability.
          </Callout>
          <Link className="mt-4 inline-flex text-xs font-semibold text-teal-700 hover:text-teal-800" to="/predictive">
            Inspect model evaluation →
          </Link>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card
          title="Top review priorities"
          subtitle="Ranked by model probability percentile with deterministic tie-breaking"
          className="xl:col-span-2"
          bodyClassName="p-0"
          actions={<Link className="text-xs font-semibold text-teal-700 hover:text-teal-800" to="/risk">View all</Link>}
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3">Rank</th>
                  <th className="px-4 py-3">Asset</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Model probability</th>
                  <th className="px-4 py-3">Criticality</th>
                  <th className="px-5 py-3">Driver</th>
                </tr>
              </thead>
              <tbody>
                {data.top_risks.slice(0, 7).map((risk) => (
                  <tr key={risk.asset_id} className="table-row">
                    <td className="table-cell font-mono text-xs text-ink-500">#{risk.rank}</td>
                    <td className="table-cell">
                      <Link className="font-semibold text-ink-900 hover:text-teal-700" to={`/risk?asset=${risk.asset_id}`}>
                        {risk.asset_id}
                      </Link>
                      <p className="text-[11px] text-ink-500">{risk.asset_name ?? titleCase(risk.asset_type)}</p>
                    </td>
                    <td className="table-cell"><PriorityBadge priority={risk.review_priority} /></td>
                    <td className="table-cell">
                      <span className="font-semibold">{formatProbability(risk.model_probability)}</span>
                      <p className="text-[11px] text-ink-500">{formatPercent(risk.model_probability_percentile ?? 0, 0)} percentile</p>
                    </td>
                    <td className="table-cell">
                      <Badge tone={risk.criticality.tier === "critical" ? "red" : risk.criticality.tier === "high" ? "amber" : "slate"}>
                        {risk.criticality.label}
                      </Badge>
                    </td>
                    <td className="table-cell text-xs text-ink-500">{titleCase(risk.primary_drivers[0])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Failure profile" subtitle="Synthetic incidents by severity" bodyClassName="p-5">
            <div className="space-y-3">
              {severityData.map((entry) => (
                <div key={entry.name}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-ink-500">{entry.name}</span>
                    <span className="font-semibold text-ink-700">{entry.value}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-ink-100">
                    <div
                      className="h-1.5 rounded-full bg-signal-red/80"
                      style={{ width: `${(entry.value / Math.max(1, ...severityData.map((item) => item.value))) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <dl className="mt-5 grid grid-cols-2 gap-4">
              <KeyValue label="Inspections">{formatNumber(data.inspections.total)}</KeyValue>
              <KeyValue label="Coverage">{`${data.inspections.coverage_percent}%`}</KeyValue>
              <KeyValue label="Assets inspected">{formatNumber(data.inspections.assets_inspected)}</KeyValue>
              <KeyValue label="Latest">{formatDate(data.inspections.latest_inspection)}</KeyValue>
            </dl>
          </Card>

          <Card title="Data freshness" subtitle="Latest source timestamps" bodyClassName="p-5">
            <dl className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <dt className="text-ink-500">Telemetry</dt>
                <dd className="font-medium text-ink-700">{formatDateTime(data.freshness.latest_telemetry)}</dd>
              </div>
              <div className="flex items-center justify-between text-xs">
                <dt className="text-ink-500">Failures</dt>
                <dd className="font-medium text-ink-700">{formatDateTime(data.freshness.latest_failure)}</dd>
              </div>
              <div className="flex items-center justify-between text-xs">
                <dt className="text-ink-500">Inspections</dt>
                <dd className="font-medium text-ink-700">{formatDateTime(data.freshness.latest_inspection)}</dd>
              </div>
              <div className="flex items-center justify-between text-xs">
                <dt className="text-ink-500">Weather</dt>
                <dd className="font-medium text-ink-700">{formatDateTime(data.freshness.latest_weather)}</dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card
          title="Recent engineering decisions"
          subtitle="Human review activity and current status"
          bodyClassName="p-0"
          actions={<Link className="text-xs font-semibold text-teal-700" to="/decisions">Open review</Link>}
        >
          {data.decisions.recent.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-ink-500">No decisions recorded yet.</p>
          ) : (
            <ul className="divide-y divide-ink-300/50">
              {data.decisions.recent.map((decision) => (
                <li key={decision.decision_id} className="flex items-center justify-between gap-3 px-5 py-3.5">
                  <div>
                    <p className="text-sm font-semibold text-ink-900">{decision.asset_id}</p>
                    <p className="text-[11px] text-ink-500">
                      {titleCase(decision.asset_type)} · {decision.reviewer} · {formatDateTime(decision.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={decision.decision_status} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Pipeline lineage"
          subtitle="Most recent ingestion runs and quality posture"
          bodyClassName="p-0"
          actions={<Link className="text-xs font-semibold text-teal-700" to="/governance">Governance</Link>}
        >
          <div className="divide-y divide-ink-300/50">
            {data.recent_ingestion.slice(0, 4).map((run) => (
              <div key={run.run_id} className="flex items-start justify-between gap-3 px-5 py-3.5">
                <div>
                  <p className="text-sm font-medium text-ink-900">{run.source_name}</p>
                  <p className="text-[11px] text-ink-500">
                    {formatNumber(run.rows_inserted)} inserted · {formatNumber(run.rows_updated)} updated · {formatNumber(run.rows_rejected)} rejected
                  </p>
                  <p className="text-[11px] text-ink-500">{formatDateTime(run.started_at)}</p>
                </div>
                <StatusBadge status={run.status} />
              </div>
            ))}
          </div>
          <div className="border-t border-ink-300/50 px-5 py-3">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 text-ink-500">
                <IconDatabase className="h-3.5 w-3.5" /> Knowledge corpus
              </span>
              <span className="font-semibold text-ink-700">
                {formatNumber(data.knowledge.documents)} docs · {formatNumber(data.knowledge.chunks)} chunks
              </span>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
        <IconPulse className="h-3.5 w-3.5 text-teal-600" />
        Snapshot reference {formatDate(data.risks.prediction_cutoffs[0])} · {formatNumber(data.risk_record_count)} risk records ·{" "}
        <span className="inline-flex items-center gap-1">
          <IconRisk className="h-3.5 w-3.5" /> {formatNumber(data.risks.data_quality_warning_count)} data-quality flags
        </span>
      </div>
    </>
  );
}
