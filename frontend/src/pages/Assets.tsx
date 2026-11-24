import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { IconChevron, IconFilter, IconRefresh } from "../components/Icons";
import {
  Badge,
  Card,
  Drawer,
  EmptyBlock,
  ErrorBlock,
  Field,
  KeyValue,
  LoadingBlock,
  PageHeader,
  Pagination,
  PriorityBadge,
  SearchField,
  StatusBadge,
} from "../components/ui";
import { useApi } from "../lib/useApi";
import type { AssetFilters, AssetProfile, Asset, Page } from "../lib/types";
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatProbability,
  titleCase,
} from "../lib/format";

const PAGE_SIZE = 25;

const SORT_COLUMNS: { key: string; label: string; className?: string }[] = [
  { key: "asset_id", label: "Asset ID" },
  { key: "name", label: "Asset name" },
  { key: "asset_type", label: "Type" },
  { key: "status", label: "Status" },
  { key: "region", label: "Region" },
  { key: "install_date", label: "Installed" },
  { key: "operating_hours_cumulative", label: "Operating hours" },
];

export default function Assets() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [assetType, setAssetType] = useState("");
  const [status, setStatus] = useState("");
  const [region, setRegion] = useState("");
  const [sortBy, setSortBy] = useState("asset_id");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch, assetType, status, region, sortBy, sortDir]);

  const query = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
      sort_by: sortBy,
      sort_dir: sortDir,
    });
    if (debouncedSearch) params.set("search", debouncedSearch);
    if (assetType) params.set("asset_type", assetType);
    if (status) params.set("status", status);
    if (region) params.set("region", region);
    return params.toString();
  }, [offset, sortBy, sortDir, debouncedSearch, assetType, status, region]);

  const assets = useApi<Page<Asset>>(`/api/v1/assets?${query}`);
  const filters = useApi<AssetFilters>("/api/v1/assets/filters");
  const profile = useApi<AssetProfile>(selected ? `/api/v1/assets/${selected}/profile` : null);

  function toggleSort(key: string) {
    if (sortBy === key) {
      setSortDir((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setSortDir("asc");
    }
  }

  function clearFilters() {
    setSearch("");
    setAssetType("");
    setStatus("");
    setRegion("");
    setSortBy("asset_id");
    setSortDir("asc");
  }

  const activeFilterCount = [assetType, status, region, debouncedSearch].filter(Boolean).length;

  return (
    <>
      <PageHeader
        eyebrow="Asset intelligence"
        title="Asset Explorer"
        description="Search the full synthetic asset inventory, filter by equipment class and region, and open a complete operational profile."
        actions={
          <>
            <Badge tone="teal">{formatNumber(assets.data?.total ?? 0)} matching assets</Badge>
            <button className="btn-ghost" type="button" onClick={() => { assets.reload(); filters.reload(); }}>
              <IconRefresh className="h-4 w-4" /> Refresh
            </button>
          </>
        }
      />

      <div className="card mb-4 p-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(220px,1.5fr)_repeat(3,minmax(140px,1fr))_auto]">
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder="Search asset ID, name, or region"
          />
          <Field label="Equipment type">
            <select className="input" value={assetType} onChange={(event) => setAssetType(event.target.value)}>
              <option value="">All equipment</option>
              {filters.data?.asset_types.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.count})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Status">
            <select className="input" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All statuses</option>
              {filters.data?.statuses.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.count})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Region">
            <select className="input" value={region} onChange={(event) => setRegion(event.target.value)}>
              <option value="">All regions</option>
              {filters.data?.regions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.count})
                </option>
              ))}
            </select>
          </Field>
          <div className="flex items-end">
            <button className="btn-ghost w-full" type="button" onClick={clearFilters} disabled={activeFilterCount === 0}>
              <IconFilter className="h-4 w-4" /> Clear {activeFilterCount > 0 ? `(${activeFilterCount})` : ""}
            </button>
          </div>
        </div>
      </div>

      {assets.error ? (
        <ErrorBlock message={assets.error} onRetry={assets.reload} />
      ) : assets.loading && !assets.data ? (
        <LoadingBlock label="Loading assets" rows={8} />
      ) : (
        <Card bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead className="table-head">
                <tr>
                  {SORT_COLUMNS.map((column) => (
                    <th key={column.key} className={`px-4 py-3 ${column.className ?? ""}`}>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-ink-900"
                        onClick={() => toggleSort(column.key)}
                      >
                        {column.label}
                        <IconChevron
                          className={`h-3.5 w-3.5 transition ${sortBy === column.key ? "text-teal-600" : "text-ink-300"} ${
                            sortBy === column.key && sortDir === "desc" ? "rotate-90" : sortBy === column.key ? "-rotate-90" : ""
                          }`}
                        />
                      </button>
                    </th>
                  ))}
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {assets.data?.items.map((asset) => (
                  <tr key={asset.asset_id} className="table-row cursor-pointer" onClick={() => setSelected(asset.asset_id)}>
                    <td className="table-cell font-mono text-xs font-semibold text-ink-900">{asset.asset_id}</td>
                    <td className="table-cell">{asset.name}</td>
                    <td className="table-cell">
                      <Badge tone="slate">{titleCase(asset.asset_type)}</Badge>
                    </td>
                    <td className="table-cell"><StatusBadge status={asset.status} /></td>
                    <td className="table-cell">{asset.region ?? <span className="text-ink-500">Unassigned</span>}</td>
                    <td className="table-cell">{formatDate(asset.install_date)}</td>
                    <td className="table-cell">{formatNumber(asset.operating_hours_cumulative, { maximumFractionDigits: 0 })}</td>
                    <td className="table-cell text-right">
                      <Link
                        className="text-xs font-semibold text-teal-700 hover:text-teal-800"
                        to={`/risk?asset=${asset.asset_id}`}
                        onClick={(event) => event.stopPropagation()}
                      >
                        View risk
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!assets.loading && assets.data?.items.length === 0 && (
            <div className="p-5">
              <EmptyBlock title="No assets match these filters">
                Adjust the search term or clear the filters to return to the full inventory.
              </EmptyBlock>
            </div>
          )}
          {assets.data && (
            <div className="border-t border-ink-300/50 px-4">
              <Pagination total={assets.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
            </div>
          )}
        </Card>
      )}

      <Drawer
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={profile.data?.asset.name ?? selected ?? "Asset profile"}
        subtitle={
          profile.data ? (
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-mono">{profile.data.asset.asset_id}</span>
              <Badge tone="slate">{titleCase(profile.data.asset.asset_type)}</Badge>
              <StatusBadge status={profile.data.asset.status} />
              {profile.data.asset.region && <Badge tone="teal">{profile.data.asset.region}</Badge>}
            </span>
          ) : (
            "Loading profile…"
          )
        }
      >
        {profile.error ? (
          <ErrorBlock message={profile.error} onRetry={profile.reload} />
        ) : profile.loading || !profile.data ? (
          <LoadingBlock label="Loading asset profile" rows={6} />
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <KeyValue label="Installed">{formatDate(profile.data.asset.install_date)}</KeyValue>
              <KeyValue label="Operating hours">
                {formatNumber(profile.data.asset.operating_hours_cumulative, { maximumFractionDigits: 0 })}
              </KeyValue>
              <KeyValue label="Telemetry readings">{formatNumber(profile.data.telemetry.count)}</KeyValue>
              <KeyValue label="Latest reading">{formatDateTime(profile.data.telemetry.latest?.timestamp)}</KeyValue>
              <KeyValue label="Region">{profile.data.asset.region ?? "Unassigned"}</KeyValue>
              <KeyValue label="Synthetic">Yes</KeyValue>
            </div>

            {profile.data.risk && (
              <Card
                title="Current risk assessment"
                subtitle={`Snapshot ${formatDateTime(profile.data.risk.prediction_cutoff)}`}
                bodyClassName="p-5"
                actions={<PriorityBadge priority={profile.data.risk.review_priority} />}
              >
                <div className="grid grid-cols-2 gap-4">
                  <KeyValue label="Model probability">{formatProbability(profile.data.risk.model_probability)}</KeyValue>
                  <KeyValue label="Anomaly score">{formatProbability(profile.data.risk.anomaly_score)}</KeyValue>
                  <KeyValue label="Risk category">{titleCase(profile.data.risk.risk_category)}</KeyValue>
                  <KeyValue label="Criticality">{profile.data.risk.criticality.label}</KeyValue>
                </div>
                <p className="mt-3 text-xs leading-5 text-ink-500">
                  Driver signals: {profile.data.risk.primary_drivers.map(titleCase).join(", ") || "—"}
                </p>
                <Link className="mt-3 inline-flex text-xs font-semibold text-teal-700" to={`/risk?asset=${profile.data.asset.asset_id}`}>
                  Open full risk and explanation →
                </Link>
              </Card>
            )}

            <Card title="Latest telemetry" subtitle="Most recent synthetic sensor reading" bodyClassName="p-5">
              {profile.data.telemetry.latest ? (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <KeyValue label="Temperature">{profile.data.telemetry.latest.temperature_c ?? "—"} °C</KeyValue>
                  <KeyValue label="Load">{profile.data.telemetry.latest.load_pct ?? "—"} %</KeyValue>
                  <KeyValue label="Voltage">{profile.data.telemetry.latest.voltage_kv ?? "—"} kV</KeyValue>
                  <KeyValue label="Current">{profile.data.telemetry.latest.current_a ?? "—"} A</KeyValue>
                  <KeyValue label="Vibration">{profile.data.telemetry.latest.vibration_mm_s ?? "—"} mm/s</KeyValue>
                </div>
              ) : (
                <p className="text-sm text-ink-500">No telemetry readings are available for this asset.</p>
              )}
            </Card>

            <Card title="Recent failures" bodyClassName="p-0">
              {profile.data.recent_failures.length === 0 ? (
                <p className="px-5 py-5 text-sm text-ink-500">No failures recorded for this asset.</p>
              ) : (
                <ul className="divide-y divide-ink-300/50">
                  {profile.data.recent_failures.map((failure) => (
                    <li key={failure.failure_id} className="flex items-center justify-between gap-3 px-5 py-3">
                      <div>
                        <p className="text-sm font-medium text-ink-900">{titleCase(failure.failure_category)}</p>
                        <p className="text-[11px] text-ink-500">{formatDateTime(failure.failure_timestamp)} · {failure.downtime_hours}h downtime</p>
                      </div>
                      <Badge tone={failure.failure_severity >= 4 ? "red" : "amber"}>Severity {failure.failure_severity}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card title="Recent maintenance" bodyClassName="p-0">
              {profile.data.recent_work_orders.length === 0 ? (
                <p className="px-5 py-5 text-sm text-ink-500">No work orders recorded.</p>
              ) : (
                <ul className="divide-y divide-ink-300/50">
                  {profile.data.recent_work_orders.map((order) => (
                    <li key={order.work_order_id} className="flex items-center justify-between gap-3 px-5 py-3">
                      <div>
                        <p className="text-sm font-medium text-ink-900">{titleCase(order.work_type)} · {order.work_order_id}</p>
                        <p className="text-[11px] text-ink-500">Opened {formatDateTime(order.opened_at)}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge tone={order.priority === "critical" ? "red" : "slate"}>{order.priority}</Badge>
                        <StatusBadge status={order.status} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card title="Recent inspections" bodyClassName="p-0">
              {profile.data.recent_inspections.length === 0 ? (
                <p className="px-5 py-5 text-sm text-ink-500">No inspections recorded.</p>
              ) : (
                <ul className="divide-y divide-ink-300/50">
                  {profile.data.recent_inspections.map((inspection) => (
                    <li key={inspection.inspection_id} className="px-5 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-ink-900">{titleCase(inspection.condition)}</p>
                        <Badge tone={inspection.severity >= 4 ? "red" : inspection.severity >= 3 ? "amber" : "green"}>
                          Severity {inspection.severity}
                        </Badge>
                      </div>
                      <p className="mt-0.5 text-[11px] text-ink-500">{formatDate(inspection.inspection_date)}</p>
                      <p className="mt-1 text-xs leading-5 text-ink-500">{inspection.findings}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        )}
      </Drawer>
    </>
  );
}
