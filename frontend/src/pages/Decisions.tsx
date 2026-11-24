import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { IconAlert, IconCheck, IconDecision, IconEvidence, IconRefresh, IconSearch } from "../components/Icons";
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
  Modal,
  PageHeader,
  Pagination,
  SearchField,
  Spinner,
  StatCard,
  StatusBadge,
} from "../components/ui";
import { apiGet, apiPost } from "../lib/api";
import { useApi } from "../lib/useApi";
import type { Decision, DecisionDetail, Page, RiskItem } from "../lib/types";
import { formatDateTime, formatNumber, formatProbability, titleCase, truncate } from "../lib/format";

const PAGE_SIZE = 25;
const STATUSES = [
  "PENDING_REVIEW",
  "IN_REVIEW",
  "APPROVED",
  "REJECTED",
  "OVERRIDDEN",
  "ESCALATED",
  "DEFERRED",
];
const ASSET_TYPES = ["transformers", "substations", "circuit_breakers", "feeders"];
const RISK_CATEGORIES = ["critical", "high", "medium", "low", "predicted_failure", "predicted_no_failure"];
const ACTIVE_STATUSES = new Set(["PENDING_REVIEW", "IN_REVIEW"]);

interface DecisionSummary {
  total: number;
  active: number;
  by_status: Record<string, number>;
  synthetic: boolean;
  note: string;
}

interface KnowledgeSearchResult {
  chunk_id: string;
  document_id: string;
  title: string | null;
  revision: string | null;
  category: string | null;
  equipment: string | null;
  page_number: number | null;
  text: string;
  source_checksum: string;
  combined_score: number;
}

interface RiskDetailResponse {
  item: RiskItem;
}

export default function Decisions() {
  const [params, setParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const [createAsset, setCreateAsset] = useState(params.get("asset") ?? "");
  const [createType, setCreateType] = useState(params.get("asset_type") ?? "transformers");
  const [createReviewer, setCreateReviewer] = useState("demo-reviewer");
  const [createReason, setCreateReason] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [reviewer, setReviewer] = useState("demo-reviewer");
  const [reason, setReason] = useState("");
  const [replacement, setReplacement] = useState("high");
  const [reviewDate, setReviewDate] = useState("");
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const [evidenceQuery, setEvidenceQuery] = useState("");
  const [evidenceResults, setEvidenceResults] = useState<KnowledgeSearchResult[]>([]);
  const [evidenceSelected, setEvidenceSelected] = useState<string[]>([]);
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch, statusFilter]);

  useEffect(() => {
    if (params.get("asset")) {
      setCreateAsset(params.get("asset") ?? "");
      setCreateOpen(true);
    }
  }, [params]);

  const query = useMemo(() => {
    const searchParams = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
    });
    if (statusFilter) searchParams.set("status", statusFilter);
    if (debouncedSearch) searchParams.set("search", debouncedSearch);
    return searchParams.toString();
  }, [offset, statusFilter, debouncedSearch]);

  const decisions = useApi<Page<Decision>>(`/api/v1/decisions?${query}`);
  const summary = useApi<DecisionSummary>("/api/v1/decisions/summary");
  const detail = useApi<DecisionDetail>(selectedId ? `/api/v1/decisions/${selectedId}/detail` : null);

  function reloadAll() {
    decisions.reload();
    summary.reload();
    detail.reload();
  }

  function openDetail(id: string) {
    setSelectedId(id);
    setReason("");
    setActionMessage(null);
    setEvidenceQuery("");
    setEvidenceResults([]);
    setEvidenceSelected([]);
    setEvidenceError(null);
    setReviewDate("");
    const next = new URLSearchParams(params);
    next.set("decision", id);
    setParams(next, { replace: true });
  }

  function closeDetail() {
    setSelectedId(null);
    setActionMessage(null);
    const next = new URLSearchParams(params);
    next.delete("decision");
    setParams(next, { replace: true });
  }

  async function createDecision() {
    const assetId = createAsset.trim().toUpperCase();
    if (!assetId || !createReason.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      let risk: RiskItem | null = null;
      try {
        risk = (await apiGet<RiskDetailResponse>(`/api/v1/risk/${assetId}`)).item;
      } catch {
        risk = null;
      }
      const created = await apiPost<Decision>("/api/v1/decisions", {
        asset_id: assetId,
        asset_type: risk?.asset_type ?? createType,
        model_version: risk?.model_version ?? null,
        predicted_risk_probability: risk?.model_probability ?? null,
        risk_category: risk?.risk_category ?? null,
        anomaly_score: risk?.anomaly_score ?? null,
        reviewer: createReviewer.trim() || "demo-reviewer",
        reason: createReason.trim(),
      });
      setCreateOpen(false);
      setCreateReason("");
      reloadAll();
      openDetail(created.decision_id);
    } catch (cause) {
      setCreateError(cause instanceof Error ? cause.message : "Decision creation failed.");
    } finally {
      setCreating(false);
    }
  }

  async function runAction(action: "review" | "approve" | "reject" | "escalate" | "defer" | "override") {
    if (!selectedId) return;
    if (!reason.trim()) {
      setActionMessage({ tone: "error", text: "A written rationale is required for every review action." });
      return;
    }
    setActionBusy(action);
    setActionMessage(null);
    try {
      const body: Record<string, unknown> = {
        reviewer: reviewer.trim() || "demo-reviewer",
        reason: reason.trim(),
      };
      if (action === "override") body.replacement_risk_category = replacement;
      if (action === "defer" && reviewDate) body.review_date = new Date(reviewDate).toISOString();
      await apiPost<Decision>(`/api/v1/decisions/${selectedId}/${action}`, body);
      setReason("");
      setActionMessage({ tone: "success", text: `Action ${action.toUpperCase()} recorded in the audit trail.` });
      reloadAll();
    } catch (cause) {
      setActionMessage({ tone: "error", text: cause instanceof Error ? cause.message : "The action failed." });
    } finally {
      setActionBusy(null);
    }
  }

  async function searchEvidence() {
    if (!evidenceQuery.trim()) return;
    setEvidenceBusy(true);
    setEvidenceError(null);
    try {
      const results = await apiPost<KnowledgeSearchResult[]>("/api/v1/knowledge/search", {
        query: evidenceQuery.trim(),
        top_k: 6,
      });
      setEvidenceResults(results);
      setEvidenceSelected(results.slice(0, 2).map((item) => item.chunk_id));
    } catch (cause) {
      setEvidenceError(cause instanceof Error ? cause.message : "Evidence search failed.");
      setEvidenceResults([]);
    } finally {
      setEvidenceBusy(false);
    }
  }

  async function attachEvidence() {
    if (!selectedId || evidenceSelected.length === 0) return;
    setEvidenceBusy(true);
    setEvidenceError(null);
    try {
      const payload = evidenceResults
        .filter((item) => evidenceSelected.includes(item.chunk_id))
        .map((item) => ({
          document_id: item.document_id,
          chunk_id: item.chunk_id,
          document_title: item.title ?? "Untitled document",
          revision: item.revision ?? "unknown",
          page_number: item.page_number,
          excerpt: truncate(item.text, 500),
          source_checksum: item.source_checksum,
        }));
      await apiPost(`/api/v1/decisions/${selectedId}/evidence`, { evidence: payload });
      setEvidenceResults([]);
      setEvidenceSelected([]);
      setEvidenceQuery("");
      setActionMessage({ tone: "success", text: "Evidence attached to the decision record." });
      detail.reload();
    } catch (cause) {
      setEvidenceError(cause instanceof Error ? cause.message : "Evidence could not be attached.");
    } finally {
      setEvidenceBusy(false);
    }
  }

  const decision = detail.data?.decision;
  const canReview = decision?.decision_status === "PENDING_REVIEW";
  const canAct = decision?.decision_status === "IN_REVIEW";
  const counts = summary.data?.by_status ?? {};

  return (
    <>
      <PageHeader
        eyebrow="Evidence & action"
        title="Engineering Decision Review"
        description="Every model signal becomes a human-owned decision record. Reviewers must record a written rationale before approving, rejecting, escalating, deferring, or overriding a recommendation."
        actions={
          <>
            <Badge tone="teal">Human-in-the-loop</Badge>
            <button className="btn-ghost" type="button" onClick={reloadAll}>
              <IconRefresh className="h-4 w-4" /> Refresh
            </button>
            <button className="btn-accent" type="button" onClick={() => setCreateOpen(true)}>
              <IconDecision className="h-4 w-4" /> New decision
            </button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Decision records" value={formatNumber(summary.data?.total)} hint="Persisted in PostgreSQL with full audit history" icon={<IconDecision className="h-5 w-5" />} />
        <StatCard label="Awaiting action" value={formatNumber(summary.data?.active)} hint="Pending review or in review" tone="amber" icon={<IconAlert className="h-5 w-5" />} />
        <StatCard label="Approved" value={formatNumber(counts.APPROVED ?? 0)} hint="Approved with a recorded rationale" tone="green" icon={<IconCheck className="h-5 w-5" />} />
        <StatCard label="Escalated / deferred" value={formatNumber((counts.ESCALATED ?? 0) + (counts.DEFERRED ?? 0))} hint="Held for further engineering review" tone="red" icon={<IconEvidence className="h-5 w-5" />} />
      </div>

      <div className="card mt-4 p-4">
        <div className="grid gap-3 sm:grid-cols-[minmax(220px,1.6fr)_minmax(160px,1fr)_auto]">
          <SearchField value={search} onChange={setSearch} placeholder="Search by asset ID" />
          <Field label="Status">
            <select className="input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {titleCase(value)} ({counts[value] ?? 0})
                </option>
              ))}
            </select>
          </Field>
          <div className="flex items-end">
            <button
              type="button"
              className="btn-ghost w-full"
              disabled={!statusFilter && !search}
              onClick={() => {
                setStatusFilter("");
                setSearch("");
              }}
            >
              Clear filters
            </button>
          </div>
        </div>
      </div>

      {decisions.error ? (
        <div className="mt-4"><ErrorBlock message={decisions.error} onRetry={decisions.reload} /></div>
      ) : decisions.loading && !decisions.data ? (
        <div className="mt-4"><LoadingBlock rows={8} label="Loading decision queue" /></div>
      ) : (
        <Card className="mt-4" bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3">Decision</th>
                  <th className="px-4 py-3">Asset</th>
                  <th className="px-4 py-3">Risk category</th>
                  <th className="px-4 py-3">Probability</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Reviewer</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {decisions.data?.items.map((item) => (
                  <tr
                    key={item.decision_id}
                    className="table-row cursor-pointer"
                    onClick={() => openDetail(item.decision_id)}
                  >
                    <td className="table-cell font-mono text-xs text-ink-500">{item.decision_id.slice(0, 8)}</td>
                    <td className="table-cell">
                      <p className="font-semibold text-ink-900">{item.asset_id}</p>
                      <p className="text-[11px] text-ink-500">{titleCase(item.asset_type)}</p>
                    </td>
                    <td className="table-cell">{item.risk_category ? <Badge tone="slate">{titleCase(item.risk_category)}</Badge> : <span className="text-xs text-ink-500">—</span>}</td>
                    <td className="table-cell">{formatProbability(item.predicted_risk_probability)}</td>
                    <td className="table-cell"><StatusBadge status={item.decision_status} /></td>
                    <td className="table-cell">{item.reviewer}</td>
                    <td className="table-cell text-xs text-ink-500">{formatDateTime(item.created_at)}</td>
                    <td className="table-cell text-right text-xs font-semibold text-teal-700">
                      {ACTIVE_STATUSES.has(item.decision_status) ? "Review →" : "Open →"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!decisions.loading && decisions.data?.items.length === 0 && (
            <div className="p-5">
              <EmptyBlock title="No decisions match this view">
                Create a decision from the risk workspace or with the New decision action above.
              </EmptyBlock>
            </div>
          )}
          {decisions.data && (
            <div className="border-t border-ink-300/50 px-4">
              <Pagination total={decisions.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
            </div>
          )}
        </Card>
      )}

      <Callout tone="blue" title="Governance guardrail">
        {summary.data?.note ?? "The platform never auto-approves a decision. Every transition writes an immutable audit event with reviewer, rationale, and prediction snapshot."}
      </Callout>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create a decision record"
        subtitle="The system captures the current risk snapshot when the record is created. It does not act on the asset."
      >
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Asset ID" hint="The risk snapshot is loaded automatically when available.">
              <input className="input" value={createAsset} onChange={(event) => setCreateAsset(event.target.value.toUpperCase())} placeholder="CB-00348" />
            </Field>
            <Field label="Asset type">
              <select className="input" value={createType} onChange={(event) => setCreateType(event.target.value)}>
                {ASSET_TYPES.map((type) => (
                  <option key={type} value={type}>{titleCase(type)}</option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Reviewer">
            <input className="input" value={createReviewer} onChange={(event) => setCreateReviewer(event.target.value)} />
          </Field>
          <Field label="Reason for opening the decision">
            <textarea
              className="input min-h-[88px]"
              value={createReason}
              onChange={(event) => setCreateReason(event.target.value)}
              placeholder="State the observed condition and why engineering review is required."
            />
          </Field>
          {createError && <Callout tone="red">{createError}</Callout>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn-ghost" onClick={() => setCreateOpen(false)}>Cancel</button>
            <button
              type="button"
              className="btn-accent"
              disabled={creating || !createAsset.trim() || !createReason.trim()}
              onClick={createDecision}
            >
              {creating ? <Spinner /> : <IconDecision className="h-4 w-4" />}
              Create and review
            </button>
          </div>
        </div>
      </Modal>

      <Drawer
        open={Boolean(selectedId)}
        onClose={closeDetail}
        width="max-w-3xl"
        title={decision ? `${decision.asset_id} · ${titleCase(decision.asset_type)}` : selectedId ?? "Decision"}
        subtitle={
          decision ? (
            <span className="flex flex-wrap items-center gap-2">
              <StatusBadge status={decision.decision_status} />
              <span className="font-mono text-[10px]">{decision.decision_id}</span>
              <span>{decision.reviewer}</span>
            </span>
          ) : (
            "Loading decision record…"
          )
        }
        footer={
          decision ? (
            <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] text-ink-500">
              <span>Created {formatDateTime(decision.created_at)} · updated {formatDateTime(decision.updated_at)}</span>
              <Link className="font-semibold text-teal-700" to={`/risk?asset=${decision.asset_id}`}>Open asset risk →</Link>
            </div>
          ) : null
        }
      >
        {detail.error ? (
          <ErrorBlock message={detail.error} onRetry={detail.reload} />
        ) : detail.loading || !detail.data || !decision ? (
          <LoadingBlock rows={8} label="Loading decision record" />
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <KeyValue label="Risk category">{decision.risk_category ? titleCase(decision.risk_category) : "—"}</KeyValue>
              <KeyValue label="Probability">{formatProbability(decision.predicted_risk_probability)}</KeyValue>
              <KeyValue label="Anomaly score">{decision.anomaly_score === null ? "—" : decision.anomaly_score.toFixed(2)}</KeyValue>
              <KeyValue label="Model version"><span className="font-mono text-[10px]">{decision.model_version ?? "—"}</span></KeyValue>
            </div>

            <Card title="Decision rationale" bodyClassName="p-5">
              <p className="text-sm leading-6 text-ink-700">{decision.decision_reason ?? "No rationale recorded."}</p>
              {decision.replacement_risk_category && (
                <p className="mt-2 text-xs text-ink-500">Overridden category: <span className="font-semibold text-ink-700">{titleCase(decision.replacement_risk_category)}</span></p>
              )}
              {detail.data.asset && (
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <KeyValue label="Asset name">{detail.data.asset.name}</KeyValue>
                  <KeyValue label="Region">{detail.data.asset.region ?? "Unassigned"}</KeyValue>
                  <KeyValue label="Asset status">{titleCase(detail.data.asset.status)}</KeyValue>
                  <KeyValue label="Current risk">{detail.data.current_risk ? titleCase(detail.data.current_risk.risk_category) : "—"}</KeyValue>
                </div>
              )}
            </Card>

            {(canReview || canAct) && (
              <Card
                title={canReview ? "Start review" : "Record a review outcome"}
                subtitle="A rationale is mandatory. State what evidence was inspected and why the outcome is justified."
                bodyClassName="p-5"
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Reviewer">
                    <input className="input" value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
                  </Field>
                  {canAct && (
                    <Field label="Override category" hint="Used only for the Override action.">
                      <select className="input" value={replacement} onChange={(event) => setReplacement(event.target.value)}>
                        {RISK_CATEGORIES.map((value) => (
                          <option key={value} value={value}>{titleCase(value)}</option>
                        ))}
                      </select>
                    </Field>
                  )}
                </div>
                <div className="mt-3">
                  <Field label="Rationale">
                    <textarea
                      className="input min-h-[88px]"
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      placeholder="Example: reviewed dissolved-gas trend, inspection findings, and maintenance history before deciding."
                    />
                  </Field>
                </div>
                {canAct && (
                  <div className="mt-3 max-w-xs">
                    <Field label="Defer until (optional)">
                      <input type="date" className="input" value={reviewDate} onChange={(event) => setReviewDate(event.target.value)} />
                    </Field>
                  </div>
                )}
                {actionMessage && <div className="mt-3"><Callout tone={actionMessage.tone === "success" ? "green" : "red"}>{actionMessage.text}</Callout></div>}
                <div className="mt-4 flex flex-wrap gap-2">
                  {canReview && (
                    <button type="button" className="btn-accent" disabled={actionBusy !== null || !reason.trim()} onClick={() => runAction("review")}>
                      {actionBusy === "review" ? <Spinner /> : <IconSearch className="h-4 w-4" />} Start review
                    </button>
                  )}
                  {canAct && (
                    <>
                      <button type="button" className="btn-accent" disabled={actionBusy !== null || !reason.trim()} onClick={() => runAction("approve")}>
                        Approve
                      </button>
                      <button type="button" className="btn-danger" disabled={actionBusy !== null || !reason.trim()} onClick={() => runAction("reject")}>
                        Reject
                      </button>
                      <button type="button" className="btn-ghost" disabled={actionBusy !== null || !reason.trim()} onClick={() => runAction("escalate")}>
                        Escalate
                      </button>
                      <button type="button" className="btn-ghost" disabled={actionBusy !== null || !reason.trim()} onClick={() => runAction("defer")}>
                        Defer
                      </button>
                      <button type="button" className="btn-ghost" disabled={actionBusy !== null || !reason.trim()} onClick={() => runAction("override")}>
                        Override → {titleCase(replacement)}
                      </button>
                    </>
                  )}
                </div>
                {!canReview && !canAct && (
                  <p className="mt-3 text-xs text-ink-500">This decision is final. No further transitions are permitted.</p>
                )}
              </Card>
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Audit history" subtitle="Append-only transition record" bodyClassName="p-0">
                {detail.data.history.length === 0 ? (
                  <p className="px-5 py-5 text-sm text-ink-500">No events recorded.</p>
                ) : (
                  <ol className="space-y-0 divide-y divide-ink-300/50">
                    {detail.data.history.map((event) => (
                      <li key={event.event_id} className="px-5 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-semibold text-ink-900">{titleCase(event.action)}</p>
                          <StatusBadge status={event.new_status} />
                        </div>
                        <p className="mt-0.5 text-[11px] text-ink-500">{event.reviewer} · {formatDateTime(event.timestamp)}</p>
                        {event.reason && <p className="mt-1 text-xs leading-5 text-ink-600">{event.reason}</p>}
                      </li>
                    ))}
                  </ol>
                )}
              </Card>

              <Card title="Attached evidence" subtitle="Validated knowledge chunks linked to this decision" bodyClassName="p-0">
                {detail.data.evidence.length === 0 ? (
                  <p className="px-5 py-5 text-sm text-ink-500">No evidence attached yet.</p>
                ) : (
                  <ul className="divide-y divide-ink-300/50">
                    {detail.data.evidence.map((item) => (
                      <li key={item.id} className="px-5 py-3">
                        <p className="text-xs font-semibold text-ink-900">{item.document_title}</p>
                        <p className="text-[10px] text-ink-500">{item.revision} · page {item.page_number ?? "n/a"} · checksum {item.source_checksum.slice(0, 12)}</p>
                        <p className="mt-1 text-[11px] leading-5 text-ink-600">{truncate(item.excerpt, 220)}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <Card title="Attach supporting evidence" subtitle="Search the synthetic corpus and link validated chunks" bodyClassName="p-5">
              <div className="flex gap-2">
                <input
                  className="input"
                  value={evidenceQuery}
                  onChange={(event) => setEvidenceQuery(event.target.value)}
                  onKeyDown={(event) => { if (event.key === "Enter") searchEvidence(); }}
                  placeholder="e.g. transformer oil sampling interval"
                />
                <button type="button" className="btn-primary shrink-0" onClick={searchEvidence} disabled={evidenceBusy || !evidenceQuery.trim()}>
                  <IconSearch className="h-4 w-4" /> Search
                </button>
              </div>
              {evidenceError && <div className="mt-3"><Callout tone="red">{evidenceError}</Callout></div>}
              {evidenceResults.length > 0 && (
                <>
                  <ul className="mt-3 space-y-2">
                    {evidenceResults.map((result) => (
                      <li key={result.chunk_id} className="rounded-xl border border-ink-300/60 px-4 py-3">
                        <label className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 rounded border-ink-300 text-teal-600"
                            checked={evidenceSelected.includes(result.chunk_id)}
                            onChange={(event) =>
                              setEvidenceSelected((current) =>
                                event.target.checked ? [...current, result.chunk_id] : current.filter((id) => id !== result.chunk_id),
                              )
                            }
                          />
                          <span>
                            <span className="block text-xs font-semibold text-ink-900">{result.title ?? "Untitled document"}</span>
                            <span className="block text-[10px] text-ink-500">{result.category ?? "uncategorised"} · page {result.page_number ?? "n/a"} · score {result.combined_score.toFixed(3)}</span>
                            <span className="mt-1 block text-[11px] leading-5 text-ink-600">{truncate(result.text, 240)}</span>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                  <button type="button" className="btn-accent mt-3" disabled={evidenceBusy || evidenceSelected.length === 0} onClick={attachEvidence}>
                    {evidenceBusy ? <Spinner /> : <IconEvidence className="h-4 w-4" />}
                    Attach {evidenceSelected.length} selected
                  </button>
                </>
              )}
            </Card>
          </div>
        )}
      </Drawer>
    </>
  );
}
