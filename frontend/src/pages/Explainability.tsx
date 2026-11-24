import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { IconAlert, IconExplain, IconInfo, IconRefresh, IconSearch } from "../components/Icons";
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
  PriorityBadge,
  StatCard,
} from "../components/ui";
import { useApi } from "../lib/useApi";
import type { Explanation, RiskListResponse } from "../lib/types";
import { formatDateTime, formatNumber, formatProbability, formatScore, prettyFeature, titleCase } from "../lib/format";

interface GlobalExplanation {
  model_available: boolean;
  preferred_model: { label: string; model_name: string; model_version: string | null } | null;
  global_importance: { feature: string; label: string; importance: number }[];
  baseline: {
    artifact: string;
    created_at: string | null;
    prediction_cutoff: string | null;
    asset_count: number | null;
    feature_count: number | null;
    model_version: string | null;
    methodology: string | null;
    z_cap: number | null;
  } | null;
  methodology: Record<string, string>;
}

export default function Explainability() {
  const global = useApi<GlobalExplanation>("/api/v1/explainability/global");
  const topRisks = useApi<RiskListResponse>("/api/v1/risk?limit=6&sort=rank&direction=asc");
  const [assetId, setAssetId] = useState("");
  const [input, setInput] = useState("");
  const explanation = useApi<Explanation>(assetId ? `/api/v1/explainability/${assetId}` : null);

  useEffect(() => {
    if (!assetId && topRisks.data?.items.length) {
      const first = topRisks.data.items[0].asset_id;
      setAssetId(first);
      setInput(first);
    }
  }, [assetId, topRisks.data]);

  function submit() {
    const value = input.trim().toUpperCase();
    if (value) setAssetId(value);
  }

  const deviationData = (explanation.data?.top_deviations ?? []).slice(0, 8).map((item) => ({
    name: item.label,
    value: item.robust_z,
    fill: item.robust_z >= 10 ? "#dc2626" : item.robust_z >= 4 ? "#f59e0b" : "#06b6d4",
  }));
  const importanceData = (global.data?.global_importance ?? []).slice(0, 12).map((item) => ({
    name: item.label,
    value: item.importance,
  }));

  return (
    <>
      <PageHeader
        eyebrow="Asset intelligence"
        title="Model Explainability"
        description="Decompose a persisted risk score into feature deviations, examine global model behaviour, and read the explicit limitations of each method."
        actions={
          <>
            <Badge tone="amber">Not SHAP</Badge>
            <button className="btn-ghost" type="button" onClick={() => { global.reload(); topRisks.reload(); explanation.reload(); }}>
              <IconRefresh className="h-4 w-4" /> Refresh
            </button>
          </>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
        <div className="space-y-4">
          <Card title="Asset selector" subtitle="Inspect the top-ranked asset or search by identifier" bodyClassName="p-5">
            <div className="flex gap-2">
              <input
                className="input"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter") submit(); }}
                placeholder="T-00001, CB-00348…"
                aria-label="Asset identifier"
              />
              <button type="button" className="btn-primary shrink-0" onClick={submit}>
                <IconSearch className="h-4 w-4" /> Load
              </button>
            </div>
            <div className="mt-4">
              <p className="label">Top review priorities</p>
              <div className="flex flex-wrap gap-2">
                {topRisks.loading && <span className="text-xs text-ink-500">Loading…</span>}
                {topRisks.data?.items.map((item) => (
                  <button
                    key={item.asset_id}
                    type="button"
                    onClick={() => { setAssetId(item.asset_id); setInput(item.asset_id); }}
                    className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition ${
                      assetId === item.asset_id
                        ? "border-teal-500 bg-teal-50 text-teal-800"
                        : "border-ink-300 bg-white text-ink-700 hover:border-teal-400"
                    }`}
                  >
                    <PriorityBadge priority={item.review_priority} />
                    {item.asset_id}
                  </button>
                ))}
              </div>
            </div>
          </Card>

          {global.error ? (
            <ErrorBlock message={global.error} onRetry={global.reload} />
          ) : global.loading || !global.data ? (
            <LoadingBlock rows={5} label="Loading model explanation context" />
          ) : (
            <>
              <Card title="Baseline artifact" subtitle="Population reference used for deviations" bodyClassName="p-5">
                <dl className="grid grid-cols-2 gap-4">
                  <KeyValue label="Assets">{formatNumber(global.data.baseline?.asset_count)}</KeyValue>
                  <KeyValue label="Features">{formatNumber(global.data.baseline?.feature_count)}</KeyValue>
                  <KeyValue label="Cutoff">{formatDateTime(global.data.baseline?.prediction_cutoff)}</KeyValue>
                  <KeyValue label="Z cap">{global.data.baseline?.z_cap ?? "—"}</KeyValue>
                  <KeyValue label="Created">{formatDateTime(global.data.baseline?.created_at)}</KeyValue>
                  <KeyValue label="Model version"><span className="font-mono text-[10px]">{global.data.baseline?.model_version ?? "—"}</span></KeyValue>
                </dl>
                <p className="mt-3 break-all font-mono text-[10px] text-ink-500">{global.data.baseline?.artifact ?? "Baseline missing"}</p>
                <p className="mt-2 text-[11px] leading-5 text-ink-500">{global.data.baseline?.methodology}</p>
              </Card>

              <Callout tone="blue" title="How to read this page">
                {global.data.methodology.deviation} {global.data.methodology.importance}
              </Callout>
            </>
          )}
        </div>

        <div className="space-y-4">
          {explanation.error ? (
            <ErrorBlock message={explanation.error} onRetry={explanation.reload} />
          ) : explanation.loading || !explanation.data ? (
            <LoadingBlock rows={8} label="Loading asset explanation" />
          ) : explanation.data.unavailable ? (
            <Card title="Explanation unavailable">
              <EmptyBlock title="This asset cannot be explained yet">{explanation.data.reason}</EmptyBlock>
            </Card>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <StatCard
                  label="Model probability"
                  value={formatProbability(explanation.data.probability)}
                  hint={`Threshold ${explanation.data.model_threshold ?? "—"}`}
                  icon={<IconExplain className="h-5 w-5" />}
                />
                <StatCard
                  label="Anomaly magnitude"
                  value={formatScore(explanation.data.anomaly_score)}
                  hint={`Capped at ${explanation.data.z_cap ?? 50}`}
                  tone="amber"
                />
                <StatCard
                  label="Criticality"
                  value={explanation.data.criticality?.label ?? "—"}
                  hint={`Score ${explanation.data.criticality?.score ?? "—"}`}
                  tone="blue"
                />
              </div>

              <Card
                title={`${explanation.data.asset_id} · ${explanation.data.asset_name ?? titleCase(explanation.data.asset_type)}`}
                subtitle={`Snapshot ${formatDateTime(explanation.data.prediction_cutoff)} · ${explanation.data.status ?? "status unknown"}`}
                actions={<Badge tone="teal">{titleCase(explanation.data.risk_category)}</Badge>}
                bodyClassName="p-5"
              >
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={deviationData} layout="vertical" margin={{ left: 10, right: 24, top: 4, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e4e7ec" />
                      <XAxis type="number" tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={190}
                        tick={{ fontSize: 10, fill: "#475467" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(value: number) => [`z = ${Number(value).toFixed(2)}`, "Deviation"]}
                        contentStyle={{ borderRadius: 12, borderColor: "#e4e7ec", fontSize: 12 }}
                      />
                      <Bar dataKey="value" radius={[0, 5, 5, 0]} barSize={16}>
                        {deviationData.map((entry) => (
                          <Cell key={entry.name} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-2 text-[11px] leading-5 text-ink-500">
                  {explanation.data.all_deviation_count ?? deviationData.length} numeric features were compared. The eight largest deviations are shown;
                  bars are absolute robust z-scores capped at {explanation.data.z_cap ?? 50}.
                </p>
              </Card>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card title="Data quality" bodyClassName="p-5">
                  <div className="space-y-3">
                    <div>
                      <div className="mb-1 flex justify-between text-xs"><span className="text-ink-500">Telemetry coverage</span><span className="font-semibold">{formatProbability(explanation.data.data_quality?.telemetry_coverage_ratio as number | undefined)}</span></div>
                      <MeterBar value={explanation.data.data_quality?.telemetry_coverage_ratio as number | undefined} />
                    </div>
                    <div>
                      <div className="mb-1 flex justify-between text-xs"><span className="text-ink-500">Missing-value ratio</span><span className="font-semibold">{formatProbability(explanation.data.data_quality?.missing_value_ratio as number | undefined)}</span></div>
                      <MeterBar value={explanation.data.data_quality?.missing_value_ratio as number | undefined} tone="amber" />
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-ink-500">History groups</span>
                      <span className="font-semibold">{String(explanation.data.data_quality?.history_group_count ?? "—")} / 3</span>
                    </div>
                  </div>
                  {explanation.data.warnings && explanation.data.warnings.length > 0 && (
                    <ul className="mt-4 space-y-1.5 text-[11px] leading-5 text-ink-500">
                      {explanation.data.warnings.map((warning) => (
                        <li key={warning} className="flex gap-2">
                          <IconAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal-amber" />
                          {warning}
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>

                <Card title="Criticality rationale" bodyClassName="p-5">
                  <p className="text-2xl font-semibold text-ink-900">{explanation.data.criticality?.score ?? "—"}</p>
                  <p className="text-xs text-ink-500">{explanation.data.criticality?.label ?? "Unavailable"} consequence tier</p>
                  <ul className="mt-3 space-y-1.5 text-xs leading-5 text-ink-500">
                    {explanation.data.criticality?.reasons.length ? (
                      explanation.data.criticality.reasons.map((reason) => (
                        <li key={reason} className="flex gap-2"><span className="text-teal-600">•</span>{reason}</li>
                      ))
                    ) : (
                      <li>No high-consequence attributes were identified by the configured rules.</li>
                    )}
                  </ul>
                </Card>
              </div>

              <Card title="Methodology limits" bodyClassName="p-5">
                <ul className="space-y-2 text-xs leading-5 text-ink-500">
                  {Object.entries(explanation.data.methodology ?? {}).map(([key, value]) => (
                    <li key={key} className="flex gap-2">
                      <IconInfo className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />
                      <span><span className="font-semibold capitalize text-ink-700">{key.replace(/_/g, " ")}:</span> {value}</span>
                    </li>
                  ))}
                </ul>
                {explanation.data.missing_features && explanation.data.missing_features.length > 0 && (
                  <p className="mt-3 text-[11px] leading-5 text-ink-500">
                    Imputed features: {explanation.data.missing_features.slice(0, 12).map(prettyFeature).join(", ")}
                    {explanation.data.missing_features.length > 12 ? "…" : ""}
                  </p>
                )}
              </Card>
            </>
          )}
        </div>
      </div>

      {global.data && (
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <Card title="Global model importance" subtitle="Aggregated from fitted coefficients; describes model behaviour, not causation" bodyClassName="p-4">
            {importanceData.length === 0 ? (
              <EmptyBlock title="No global importance available" />
            ) : (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={importanceData} layout="vertical" margin={{ left: 12, right: 20, top: 4, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e4e7ec" />
                    <XAxis type="number" tick={{ fontSize: 10, fill: "#667085" }} axisLine={false} tickLine={false} tickFormatter={(value) => `${(value * 100).toFixed(1)}%`} />
                    <YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 10, fill: "#475467" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(value: number) => [`${(Number(value) * 100).toFixed(2)}%`, "Share"]}
                      contentStyle={{ borderRadius: 12, borderColor: "#e4e7ec", fontSize: 12 }}
                    />
                    <Bar dataKey="value" fill="#0891b2" radius={[0, 5, 5, 0]} barSize={14} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          <Card title="Reading the score" subtitle="What the platform does and does not claim" bodyClassName="p-5">
            <ul className="space-y-3 text-xs leading-5 text-ink-500">
              <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" />A high probability means the synthetic classifier ranks the asset high relative to its training cohort.</li>
              <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" />A large deviation means an observed feature is unusual against the population baseline; it may be benign.</li>
              <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" />Global importance is not local attribution. This page does not compute SHAP values.</li>
              <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" />Human reviewers must consult engineering evidence and record a reason before any decision.</li>
            </ul>
          </Card>
        </div>
      )}
      <p className="mt-4 text-[11px] text-ink-500">
        Percentiles are population-relative. Assets without a persisted probability are surfaced explicitly rather than imputed.
      </p>
    </>
  );
}
