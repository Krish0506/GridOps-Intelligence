import { useEffect, useState } from "react";
export default function Predictive() {
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    // Metrics are persisted with the trained model artifact; surface a notice.
    setMetrics({ note: "Train a model via CLI to populate metrics." });
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Predictive Analytics</h2>
      <div className="bg-white p-4 rounded shadow mb-4">
        <p className="text-sm text-slate-500">Model</p>
        <p className="font-bold">Logistic Regression (pure Python)</p>
        <p className="text-sm text-slate-500 mt-2">Synthetic evaluation metrics only — not real-world performance.</p>
      </div>
      <pre className="bg-white p-4 rounded shadow text-xs overflow-auto">{JSON.stringify(metrics, null, 2)}</pre>
    </div>
  );
}
