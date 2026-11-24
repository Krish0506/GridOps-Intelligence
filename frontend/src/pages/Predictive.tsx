import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { IconChart, IconCheck, IconDatabase, IconInfo, IconRefresh } from "../components/Icons";
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
} from "../components/ui";
import { useApi } from "../lib/useApi";
import type { Metrics, ModelSummary, PredictiveResponse } from "../lib/types";
import { formatBytes, formatDateTime, formatNumber, formatPercent } from "../lib/format";

const METRIC_KEYS: { key: keyof Metrics; label: string; invert?: boolean }[] = [
  { key: "roc_auc", label: "ROC AUC" },
  { key: "precision", label: "Precision" },
  { key: "recall", label: "Recall" },
  { key: "f1", label: "F1" },
  { key: "average_precision", label: "Avg precision" },
  { key: "brier", label: "Brier (lower better)", invert: true },
];

export default function Predictive() {
  const { data, loading, error, reload } = useApi<PredictiveResponse>("/api/v1/predictive");
  const [selectedName, setSelectedName] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedName && data?.preferred_model) setSelectedName(data.preferred_model.model_name);
  }, [data, selectedName]);

  const selected: ModelSummary | null = useMemo(() => {
    if (!data) return null;
    return data.models.find((model) => model.model_name === selectedName) ?? data.preferred_model;
  }, [data, selectedName]);

  if (loading && !data) {
    return (
      <>
        <PageHeader eyebrow="Asset intelligence" title="Predictive Analytics" description="Loading persisted model artifacts…" />
        <LoadingBlock rows={6} />
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <PageHeader eyebrow="Asset intelligence" title="Predictive Analytics" />
        <ErrorBlock message={error ?? "No predictive data was returned."} onRetry={reload} />
      </>
    );
  }

  if (!data.available || !selected) {
    return (
      <>
        <PageHeader eyebrow="Asset intelligence" title="Predictive Analytics" />
        <Card title="No trained model artifact">
          <EmptyBlock title="Model inference is unavailable">
            {data.message ?? "Train a baseline model to enable predictions."} Run{" "}
            <span className="font-mono">python -m data_engineering.cli train --model logistic_regression</span>.
          </EmptyBlock>
        </Card>
      </>
    );
  }

  const validation = selected.validation_metrics ?? {};
  const test = selected.test_metrics ?? {};
  const chartData = METRIC_KEYS.filter((metric) => metric.key !== "brier").map((metric) => ({
    name: metric.label,
    value: Number(validation[metric.key] ?? 0),
    test: Number(test[metric.key] ?? 0),
  }));

  return (
    <>
      <PageHeader
        eyebrow="Asset intelligence"
        title="Predictive Analytics"
        description="Inspect the persisted classifiers, their held-out evaluation, feature contract, and artifact lineage. Metrics describe a synthetic evaluation cohort, not field performance."
        actions={
          <>
            <Badge tone={data.available ? "green" : "red"}>{data.available ? "Artifact loaded" : "Unavailable"}</Badge>
            <button className="btn-ghost" type="button" onClick={reload}>
              <IconRefresh className="h-4 w-4" /> Refresh
            </button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Preferred model"
          value={selected.label}
          hint={selected.model_name}
          icon={<IconChart className="h-5 w-5" />}
        />
        <StatCard
          label="Validation ROC AUC"
          value={validation.roc_auc !== undefined ? Number(validation.roc_auc).toFixed(3) : "—"}
          hint={`${formatNumber(selected.split.validation_assets ?? 0)} validation assets`}
          tone="blue"
        />
        <StatCard
          label="Test recall"
          value={test.recall !== undefined ? formatPercent(Number(test.recall), 1) : "—"}
          hint={`${formatNumber(selected.split.test_assets ?? 0)} held-out test assets`}
          tone="green"
        />
        <StatCard
          label="Decision threshold"
          value={selected.threshold ?? "—"}
          hint="Tuned on validation data; persisted with the artifact"
          tone="amber"
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card title="Held-out performance" subtitle="Validation and test scores for the selected artifact" bodyClassName="p-4">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 8, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e4e7ec" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "#667085" }} axisLine={false} tickLine={false} />
                <Tooltip
                  formatter={(value: number, name: string) => [Number(value).toFixed(3), name === "test" ? "Test" : "Validation"]}
                  contentStyle={{ borderRadius: 12, borderColor: "#e4e7ec", fontSize: 12 }}
                />
                <Bar dataKey="value" name="Validation" radius={[5, 5, 0, 0]} barSize={22} fill="#0891b2" />
                <Bar dataKey="test" name="Test" radius={[5, 5, 0, 0]} barSize={22} fill="#cbd5e1" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 flex items-center gap-4 text-[11px] text-ink-500">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-teal-600" /> Validation</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-ink-300" /> Test</span>
          </div>
        </Card>

        <Card title="Metric detail" subtitle="What each number means" bodyClassName="p-0">
          <div className="divide-y divide-ink-300/50">
            {METRIC_KEYS.map((metric) => {
              const value = validation[metric.key];
              const testValue = test[metric.key];
              const numeric = value === undefined ? null : Number(value);
              return (
                <div key={metric.key} className="px-5 py-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-semibold text-ink-700">{metric.label}</span>
                    <span className="text-xs font-semibold text-ink-900">
                      {numeric === null ? "—" : metric.invert ? numeric.toFixed(4) : numeric.toFixed(3)}
                      {testValue !== undefined && (
                        <span className="ml-2 font-normal text-ink-500">test {metric.invert ? Number(testValue).toFixed(4) : Number(testValue).toFixed(3)}</span>
                      )}
                    </span>
                  </div>
                  {!metric.invert && numeric !== null && (
                    <div className="mt-1.5">
                      <MeterBar value={numeric} tone={numeric >= 0.9 ? "teal" : numeric >= 0.7 ? "blue" : "amber"} />
                    </div>
                  )}
                  <p className="mt-1.5 text-[11px] leading-4 text-ink-500">{selected.metric_explanations[metric.key] ?? ""}</p>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card title="Artifact lineage" subtitle="Persisted files and inference contract" bodyClassName="p-5">
          <dl className="grid grid-cols-2 gap-4">
            <KeyValue label="Version"><span className="font-mono text-xs">{selected.model_version ?? "—"}</span></KeyValue>
            <KeyValue label="Threshold">{selected.threshold ?? "—"}</KeyValue>
            <KeyValue label="Features">{formatNumber(selected.feature_count)}</KeyValue>
            <KeyValue label="Artifact size">{formatBytes(selected.artifact_size_bytes)}</KeyValue>
            <KeyValue label="Last modified">{formatDateTime(selected.artifact_modified_at)}</KeyValue>
            <KeyValue label="Positives / negatives">
              {formatNumber(selected.positive_count)} / {formatNumber(selected.negative_count)}
            </KeyValue>
            <KeyValue label="Train / val / test">
              {formatNumber(selected.split.train_assets ?? 0)} / {formatNumber(selected.split.validation_assets ?? 0)} /{" "}
              {formatNumber(selected.split.test_assets ?? 0)}
            </KeyValue>
            <KeyValue label="Availability"><Badge tone={selected.available ? "green" : "red"}>{selected.available ? "Available" : "Missing"}</Badge></KeyValue>
          </dl>
          <div className="mt-4 space-y-1.5 rounded-xl bg-ink-50 px-4 py-3 text-[11px] leading-5 text-ink-500">
            <p className="flex items-start gap-2">
              <IconDatabase className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />
              <span className="break-all font-mono">{selected.artifact_path}</span>
            </p>
            <p className="flex items-start gap-2">
              <IconInfo className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />
              {selected.artifact_persistence}
            </p>
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Model registry" subtitle="All persisted baseline artifacts; select one to inspect" bodyClassName="p-0">
            <ul className="divide-y divide-ink-300/50">
              {data.models.map((model) => (
                <li key={model.model_name}>
                  <button
                    type="button"
                    className={`flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left transition hover:bg-ink-50 ${
                      model.model_name === selected.model_name ? "bg-teal-50/50" : ""
                    }`}
                    onClick={() => setSelectedName(model.model_name)}
                  >
                    <div>
                      <p className="text-sm font-semibold text-ink-900">{model.label}</p>
                      <p className="font-mono text-[10px] text-ink-500">{model.model_version ?? "no artifact"}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {model.validation_metrics?.f1 !== undefined && (
                        <span className="text-xs text-ink-500">F1 {Number(model.validation_metrics.f1).toFixed(3)}</span>
                      )}
                      {model.model_name === selected.model_name && <IconCheck className="h-4 w-4 text-teal-600" />}
                      <Badge tone={model.available ? "green" : "red"}>{model.available ? "Ready" : "Missing"}</Badge>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          <Callout tone="amber" title="Evaluation context">
            {data.synthetic_warning} {selected.evaluation_context}
          </Callout>

          <Card title="Evaluation cohort" bodyClassName="p-5">
            <div className="grid grid-cols-2 gap-4">
              <KeyValue label="Dataset">{data.evaluation_dataset}</KeyValue>
              <KeyValue label="Comparison artifact">{data.comparison_available ? "Present" : "Not recorded"}</KeyValue>
            </div>
            <p className="mt-3 text-xs leading-5 text-ink-500">
              Near-perfect scores reflect deliberately separable synthetic outcomes. They are evidence that the pipeline runs, not evidence of production
              readiness or real utility performance.
            </p>
          </Card>
        </div>
      </div>

      <div className="mt-4">
        <Card title="Validation confusion matrix" subtitle="Thresholded at the persisted operating point" bodyClassName="p-5">
          {validation.confusion_matrix ? (
            <div className="grid max-w-xl grid-cols-2 gap-3">
              {[
                { label: "True negative", value: validation.confusion_matrix.true_negative, tone: "bg-signal-green-soft text-emerald-900" },
                { label: "False positive", value: validation.confusion_matrix.false_positive, tone: "bg-signal-amber-soft text-amber-900" },
                { label: "False negative", value: validation.confusion_matrix.false_negative, tone: "bg-signal-red-soft text-red-900" },
                { label: "True positive", value: validation.confusion_matrix.true_positive, tone: "bg-signal-green-soft text-emerald-900" },
              ].map((cell) => (
                <div key={cell.label} className={`rounded-xl px-5 py-4 ${cell.tone}`}>
                  <p className="text-[11px] font-semibold uppercase tracking-wide">{cell.label}</p>
                  <p className="mt-1 text-2xl font-semibold">{formatNumber(cell.value)}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyBlock title="No confusion matrix persisted">Re-train the artifact to populate validation counts.</EmptyBlock>
          )}
        </Card>
      </div>
    </>
  );
}
