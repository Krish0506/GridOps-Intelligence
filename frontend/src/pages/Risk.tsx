import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
import { IconAlert, IconDecision, IconFilter, IconRefresh, IconRisk } from "../components/Icons";
import {
  Badge,
  Callout,
  Card,
  Drawer,
  EmptyBlock,
  ErrorBlock,
  Field,
  KeyValue,
  LoadingBlock,
  MeterBar,
  PageHeader,
  Pagination,
  PriorityBadge,
  SearchField,
  StatusBadge,
  Spinner,
} from "../components/ui";
import { apiPost } from "../lib/api";
import { useApi } from "../lib/useApi";
import type { Decision, Explanation, RiskItem, RiskListResponse } from "../lib/types";
import {
  criticalityTone,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatProbability,
  formatScore,
  titleCase,
} from "../lib/format";

const PAGE_SIZE = 25;
const PRIORITIES = ["P1", "P2", "P3", "P4", "P5"];
const PRIORITY_COLORS: Record<string, string> = {
  P1: "#dc2626",
  P2: "#f59e0b",
  P3: "#2563eb",
  P4: "#06b6d4",
  P5: "#cbd5e1",
};

interface RiskDetailResponse {
  item: RiskItem;
  explanation: Explanation | null;
}

export default function Risk() {
  const [params, setParams] = useSearchParams();
  const initialAsset = params.get("asset");
  const [search, setSearch] = useState(initialAsset ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(initialAsset ?? "");
  const [assetType, setAssetType] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("rank");
  const [direction, setDirection] = useState<"asc" | "desc">("asc");
  const [offset, setOffset] = useState(0);
  const [detailAsset, setDetailAsset] = useState<string | null>(initialAsset);

  const [decisionReason, setDecisionReason] = useState("");
  const [decisionReviewer, setDecisionReviewer] = useState("demo-reviewer");
  const [decisionSaving, setDecisionSaving] = useState(false);
  const [decisionMessage, setDecisionMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch, assetType, priority, category, sort, direction]);

  useEffect(() => {
    if (initialAsset) {
      setSearch(initialAsset);
      setDetailAsset(initialAsset);
    }
  }, [initialAsset]);

  const query = useMemo(() => {
    const paramsObject = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
      sort,
      direction,
    });
    if (debouncedSearch) paramsObject.set("search", debouncedSearch);
    if (assetType) paramsObject.set("asset_type", assetType);
    if (priority) paramsObject.set("priority", priority);
    if (category) paramsObject.set("risk_category", category);
    return paramsObject.toString();
  }, [offset, sort, direction, debouncedSearch, assetType, priority, category]);

  const risks = useApi<RiskListResponse>(`/api/v1/risk?${query}`);
  const detail = useApi<RiskDetailResponse>(detailAsset ? `/api/v1/risk/${detailAsset}` : null);
  const summary = risks.data?.summary;

  function openDetail(assetId: string) {
    setDetailAsset(assetId);
    setDecisionReason("");
    setDecisionMessage(null);
    const next = new URLSearchParams(params);
    next.set("asset", assetId);
    setParams(next, { replace: true });
  }

  function closeDetail() {
    setDetailAsset(null);
    setDecisionMessage(null);
    const next = new URLSearchParams(params);
    next.delete("asset");
    setParams(next, { replace: true });
  }

  async function createDecision() {
    if (!detail.data || !decisionReason.trim()) return;
    setDecisionSaving(true);
    setDecisionMessage(null);
    try {
      await apiPost<Decision>("/api/v1/decisions", {
        asset_id: detail.data.item.asset_id,
        asset_type: detail.data.item.asset_type,
        model_version: detail.data.item.model_version,
        predicted_risk_probability: detail.data.item.model_probability,
        risk_category: detail.data.item.risk_category,
        anomaly_score: detail.data.item.anomaly_score,
        reviewer: decisionReviewer.trim() || "demo-reviewer",
        reason: decisionReason.trim(),
      });
      setDecisionReason("");
      setDecisionMessage({ tone: "success", text: "Decision created in PENDING_REVIEW. It now requires human review." });
      risks.reload();
    } catch (cause) {
      setDecisionMessage({ tone: "error", text: cause instanceof Error ? cause.message : "Decision creation failed." });
    } finally {
      setDecisionSaving(false);
    }
  }

  const priorityData = PRIORITIES.map((band) => ({
    name: band,
    value: summary?.by_priority[band] ?? 0,
  }));
  const bucketData = Object.entries(summary?.probability_buckets ?? {}).map(([bucket, value]) => ({
    name: bucket,
    value,
  }));

  return (
    <>
      <PageHeader
        eyebrow="Asset intelligence"
        title="Risk Prioritization"
        description="Review the persisted risk workspace. Model probability, anomaly magnitude, asset criticality, and data quality stay separate so reviewers can see what drives the ranking."
        actions={
          <>
            <Badge tone="teal">Snapshot {summary?.prediction_cutoffs[0] ? formatDateTime(summary.prediction_cutoffs[0]) : "—"}</Badge>
            <button className="btn-ghost" type="button" onClick={risks.reload}>
              <IconRefresh className="h-4 w-4" /> Refresh
            </button>
          </>
        }
      />

      {risks.error ? (
        <ErrorBlock message={risks.error} onRetry={risks.reload} />
      ) : risks.loading && !risks.data ? (
        <LoadingBlock rows={8} label="Loading risk workspace" />
      ) : !summary ? (
        <EmptyBlock title="No risk records">Run the operational-risk workflow to populate the risk workspace.</EmptyBlock>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="card p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-500">Ranked population</p>
              <p className="mt-3 text-3xl font-semibold text-ink-900">{formatNumber(summary.total)}</p>
              <p className="mt-2 text-xs text-ink-500">{formatNumber(summary.by_category.predicted_failure ?? 0)} flagged by the model</p>
            </div>
            <div className="card p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-500">Immediate / high review</p>
              <p className="mt-3 text-3xl font-semibold text-ink-900">
                {formatNumber((summary.by_priority.P1 ?? 0) + (summary.by_priority.P2 ?? 0))}
              </p>
              <p className="mt-2 flex items-center gap-2 text-xs text-ink-500">
                <PriorityBadge priority="P1" /> {summary.by_priority.P1 ?? 0} <PriorityBadge priority="P2" /> {summary.by_priority.P2 ?? 0}
              </p>
            </div>
            <div className="card p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-500">High / critical consequence</p>
              <p className="mt-3 text-3xl font-semibold text-ink-900">
                {formatNumber((summary.criticality.high ?? 0) + (summary.criticality.critical ?? 0))}
              </p>
              <p className="mt-2 text-xs text-ink-500">Deterministic asset-level criticality tier</p>
            </div>
            <div className="card p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-500">Data-quality warnings</p>
              <p className="mt-3 text-3xl font-semibold text-ink-900">{formatNumber(summary.data_quality_warning_count)}</p>
              <p className="mt-2 text-xs text-ink-500">Assets with sparse or missing source coverage</p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card title="Review band distribution" subtitle="Population counts, not a failure probability" bodyClassName="p-4">
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={priorityData} margin={{ left: -20, right: 8, top: 8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e7ec" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(value: number) => [formatNumber(value), "Assets"]}
                      contentStyle={{ borderRadius: 12, borderColor: "#e4e7ec", fontSize: 12 }}
                    />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={40}>
                      {priorityData.map((entry) => (
                        <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title="Model probability distribution" subtitle="Buckets across all persisted risk records" bodyClassName="p-4">
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={bucketData} margin={{ left: -20, right: 8, top: 8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e7ec" />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#667085" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(value: number) => [formatNumber(value), "Assets"]}
                      contentStyle={{ borderRadius: 12, borderColor: "#e4e7ec", fontSize: 12 }}
                    />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={30} fill="#0891b2" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="card mt-4 p-4">
            <div className="grid gap-3 lg:grid-cols-[minmax(220px,1.5fr)_repeat(3,minmax(140px,1fr))_auto]">
              <SearchField value={search} onChange={setSearch} placeholder="Search asset ID or name" />
              <Field label="Equipment">
                <select className="input" value={assetType} onChange={(event) => setAssetType(event.target.value)}>
                  <option value="">All equipment</option>
                  {risks.data?.filter_options.asset_types.map((value) => (
                    <option key={value} value={value}>{titleCase(value)}</option>
                  ))}
                </select>
              </Field>
              <Field label="Priority">
                <select className="input" value={priority} onChange={(event) => setPriority(event.target.value)}>
                  <option value="">All priorities</option>
                  {PRIORITIES.map((band) => (
                    <option key={band} value={band}>{band}</option>
                  ))}
                </select>
              </Field>
              <Field label="Model category">
                <select className="input" value={category} onChange={(event) => setCategory(event.target.value)}>
                  <option value="">All categories</option>
                  {risks.data?.filter_options.risk_categories.map((value) => (
                    <option key={value} value={value}>{titleCase(value)}</option>
                  ))}
                </select>
              </Field>
              <div className="flex items-end">
                <button
                  className="btn-ghost w-full"
                  type="button"
                  onClick={() => {
                    setSearch("");
                    setAssetType("");
                    setPriority("");
                    setCategory("");
                  }}
                >
                  <IconFilter className="h-4 w-4" /> Clear
                </button>
              </div>
            </div>
          </div>

          <Card className="mt-4" bodyClassName="p-0">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-300/50 px-5 py-3">
              <p className="text-xs text-ink-500">
                <span className="font-semibold text-ink-700">{formatNumber(risks.data?.total ?? 0)}</span> assets match the current view
              </p>
              <div className="flex items-center gap-2">
                <label className="text-[11px] text-ink-500" htmlFor="risk-sort">Sort by</label>
                <select id="risk-sort" className="input w-auto py-1.5 text-xs" value={sort} onChange={(event) => setSort(event.target.value)}>
                  <option value="rank">Review rank</option>
                  <option value="model_probability">Model probability</option>
                  <option value="anomaly_score">Anomaly score</option>
                  <option value="criticality">Criticality</option>
                  <option value="asset_id">Asset ID</option>
                </select>
                <button
                  type="button"
                  className="btn-ghost px-3 py-1.5 text-xs"
                  onClick={() => setDirection((current) => (current === "asc" ? "desc" : "asc"))}
                >
                  {direction === "asc" ? "Ascending" : "Descending"}
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px]">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3">Rank</th>
                    <th className="px-4 py-3">Asset</th>
                    <th className="px-4 py-3">Equipment</th>
                    <th className="px-4 py-3">Priority</th>
                    <th className="px-4 py-3">Model probability</th>
                    <th className="px-4 py-3">Anomaly</th>
                    <th className="px-4 py-3">Criticality</th>
                    <th className="px-4 py-3">Decision</th>
                    <th className="px-5 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {risks.data?.items.map((item) => (
                    <tr key={item.asset_id} className="table-row cursor-pointer" onClick={() => openDetail(item.asset_id)}>
                      <td className="table-cell font-mono text-xs text-ink-500">#{item.rank}</td>
                      <td className="table-cell">
                        <p className="font-semibold text-ink-900">{item.asset_id}</p>
                        <p className="text-[11px] text-ink-500">{item.asset_name ?? titleCase(item.asset_type)}</p>
                      </td>
                      <td className="table-cell"><Badge tone="slate">{titleCase(item.asset_type)}</Badge></td>
                      <td className="table-cell"><PriorityBadge priority={item.review_priority} /></td>
                      <td className="table-cell">
                        <div className="w-32">
                          <div className="mb-1 flex items-center justify-between text-xs">
                            <span className="font-semibold">{formatProbability(item.model_probability)}</span>
                            <span className="text-ink-500">{formatPercent(item.model_probability_percentile ?? 0, 0)}</span>
                          </div>
                          <MeterBar value={item.model_probability} tone={item.review_priority === "P1" ? "red" : "teal"} />
                        </div>
                      </td>
                      <td className="table-cell">
                        <span className="font-semibold">{formatScore(item.anomaly_score)}</span>
                        <p className="text-[11px] text-ink-500">robust deviation</p>
                      </td>
                      <td className="table-cell">
                        <Badge tone={criticalityTone(item.criticality.tier)}>{item.criticality.label}</Badge>
                      </td>
                      <td className="table-cell">
                        {item.latest_decision_status ? (
                          <StatusBadge status={item.latest_decision_status} />
                        ) : (
                          <span className="text-xs text-ink-500">None</span>
                        )}
                      </td>
                      <td className="table-cell text-right text-xs font-semibold text-teal-700">Review →</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!risks.loading && risks.data?.items.length === 0 && (
              <div className="p-5"><EmptyBlock title="No risk records match these filters" /></div>
            )}
            {risks.data && (
              <div className="border-t border-ink-300/50 px-4">
                <Pagination total={risks.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
              </div>
            )}
          </Card>

          <details className="mt-4 rounded-2xl border border-ink-300/70 bg-white px-5 py-4 text-sm shadow-card">
            <summary className="cursor-pointer text-xs font-semibold text-ink-700">How the review priority is assigned</summary>
            <ul className="mt-3 space-y-1.5 text-xs leading-5 text-ink-500">
              {summary.priority_rules.map((rule) => (
                <li key={rule} className="flex gap-2"><span className="text-teal-600">•</span>{rule}</li>
              ))}
              <li className="flex gap-2"><span className="text-teal-600">•</span>Percentiles use deterministic tie-breaking by anomaly, then asset ID; this is a review aid, not a calibrated probability.</li>
            </ul>
          </details>
        </>
      )}

      <Drawer
        open={Boolean(detailAsset)}
        onClose={closeDetail}
        width="max-w-3xl"
        title={detail.data ? `${detail.data.item.asset_id} · ${detail.data.item.asset_name ?? titleCase(detail.data.item.asset_type)}` : detailAsset ?? "Risk detail"}
        subtitle={
          detail.data ? (
            <span className="flex flex-wrap items-center gap-2">
              <PriorityBadge priority={detail.data.item.review_priority} />
              <Badge tone={criticalityTone(detail.data.item.criticality.tier)}>{detail.data.item.criticality.label} criticality</Badge>
              <Badge tone="slate">{titleCase(detail.data.item.asset_type)}</Badge>
              {detail.data.item.region && <Badge tone="teal">{detail.data.item.region}</Badge>}
            </span>
          ) : (
            "Loading persisted risk record…"
          )
        }
        footer={
          detail.data ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-[11px] text-ink-500">
                <IconRisk className="h-4 w-4 text-teal-600" />
                Created from the persisted risk snapshot.
              </div>
              <div className="flex gap-2">
                <Link className="btn-ghost" to={`/evidence?asset=${detail.data.item.asset_id}`}>Ask evidence</Link>
                <Link className="btn-accent" to="/decisions">Open decision queue</Link>
              </div>
            </div>
          ) : null
        }
      >
        {detail.error ? (
          <ErrorBlock message={detail.error} onRetry={detail.reload} />
        ) : detail.loading || !detail.data ? (
          <LoadingBlock rows={7} label="Loading risk detail" />
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <KeyValue label="Model probability">{formatProbability(detail.data.item.model_probability)}</KeyValue>
              <KeyValue label="Percentile">{formatPercent(detail.data.item.model_probability_percentile ?? 0, 0)}</KeyValue>
              <KeyValue label="Anomaly score">{formatScore(detail.data.item.anomaly_score)}</KeyValue>
              <KeyValue label="Risk category">{titleCase(detail.data.item.risk_category)}</KeyValue>
            </div>

            <Card title="Why this asset is ranked here" subtitle="Robust deviation against the persisted population baseline" bodyClassName="p-5">
              {detail.data.explanation?.unavailable ? (
                <Callout tone="amber" title="Explanation unavailable">{detail.data.explanation.reason}</Callout>
              ) : detail.data.explanation?.top_deviations && detail.data.explanation.top_deviations.length > 0 ? (
                <div className="space-y-3">
                  {detail.data.explanation.top_deviations.slice(0, 8).map((deviation) => (
                    <div key={deviation.feature}>
                      <div className="mb-1 flex items-center justify-between gap-3 text-xs">
                        <span className="font-medium text-ink-700">{deviation.label}</span>
                        <span className="text-ink-500">
                          {deviation.direction} baseline · z {formatScore(deviation.robust_z)}
                        </span>
                      </div>
                      <MeterBar
                        value={deviation.robust_z}
                        max={detail.data?.explanation?.z_cap ?? 50}
                        tone={deviation.robust_z >= 10 ? "red" : deviation.robust_z >= 4 ? "amber" : "teal"}
                      />
                    </div>
                  ))}
                  <p className="pt-1 text-[11px] leading-5 text-ink-500">
                    {detail.data.explanation.methodology?.deviation}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-ink-500">No feature deviations were persisted for this snapshot.</p>
              )}
            </Card>

            <div className="grid gap-4 sm:grid-cols-2">
              <Card title="Criticality rationale" bodyClassName="p-5">
                <p className="text-2xl font-semibold text-ink-900">{detail.data.item.criticality.score}</p>
                <p className="text-xs text-ink-500">{detail.data.item.criticality.label} consequence tier</p>
                <ul className="mt-3 space-y-1.5 text-xs leading-5 text-ink-500">
                  {detail.data.item.criticality.reasons.length === 0 ? (
                    <li>No high-consequence attributes were identified by the configured rules.</li>
                  ) : (
                    detail.data.item.criticality.reasons.map((reason) => (
                      <li key={reason} className="flex gap-2"><span className="text-teal-600">•</span>{reason}</li>
                    ))
                  )}
                </ul>
              </Card>
              <Card title="Data quality" bodyClassName="p-5">
                {detail.data.item.data_quality_flags.length === 0 ? (
                  <Badge tone="green">No flags</Badge>
                ) : (
                  <ul className="space-y-2 text-xs leading-5 text-ink-600">
                    {detail.data.item.data_quality_flags.map((flag) => (
                      <li key={flag} className="flex gap-2">
                        <IconAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal-amber" />
                        {flag}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <Card title="Evidence and decision" subtitle="Turn the review signal into a human-owned decision" bodyClassName="p-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Reviewer">
                  <input className="input" value={decisionReviewer} onChange={(event) => setDecisionReviewer(event.target.value)} />
                </Field>
                <Field label="Risk category">{titleCase(detail.data.item.risk_category)}</Field>
              </div>
              <div className="mt-3">
                <Field label="Decision rationale" hint="Required: state what the reviewer inspected and why action is or is not warranted.">
                  <textarea
                    className="input min-h-[88px]"
                    value={decisionReason}
                    onChange={(event) => setDecisionReason(event.target.value)}
                    placeholder="Example: inspected dissolved-gas history, latest load trend, and the maintenance record before review."
                  />
                </Field>
              </div>
              {decisionMessage && (
                <div className="mt-3">
                  <Callout tone={decisionMessage.tone === "success" ? "green" : "red"}>{decisionMessage.text}</Callout>
                </div>
              )}
              <button
                type="button"
                className="btn-accent mt-3"
                onClick={createDecision}
                disabled={decisionSaving || !decisionReason.trim()}
              >
                {decisionSaving ? <Spinner /> : <IconDecision className="h-4 w-4" />}
                Create decision for review
              </button>
              {detail.data.item.latest_decision_id && (
                <p className="mt-2 text-[11px] text-ink-500">
                  Latest decision status: <StatusBadge status={detail.data.item.latest_decision_status} />
                </p>
              )}
            </Card>

            <Callout tone="amber" title="Interpretation guardrail">
              Model probability and anomaly score are different constructs. The anomaly score is an unsupervised deviation magnitude, not a calibrated
              failure probability, and neither score proves causation. Review engineering evidence before acting.
            </Callout>
          </div>
        )}
      </Drawer>
    </>
  );
}
