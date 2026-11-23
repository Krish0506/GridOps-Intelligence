import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";

interface Asset { asset_id: string; asset_type: string; status: string; region: string | null; }

export default function Overview() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ items: Asset[]; total: number }>("/api/v1/assets?limit=200")
      .then((d) => setAssets(d.items))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  const byType = assets.reduce<Record<string, number>>((acc, a) => {
    acc[a.asset_type] = (acc[a.asset_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Operations Overview</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm text-slate-500">Total assets</p>
          <p className="text-2xl font-bold">{assets.length}</p>
        </div>
        {Object.entries(byType).map(([t, n]) => (
          <div key={t} className="bg-white p-4 rounded shadow">
            <p className="text-sm text-slate-500">{t}</p>
            <p className="text-2xl font-bold">{n}</p>
          </div>
        ))}
      </div>
      <p className="text-sm text-slate-500">
        Synthetic demonstration data. Risk figures require trained model artifacts.
      </p>
    </div>
  );
}
