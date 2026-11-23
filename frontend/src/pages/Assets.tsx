import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../lib/api";

interface Asset { asset_id: string; asset_type: string; status: string; region: string | null; }

export default function Assets() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<{ items: Asset[]; total: number }>("/api/v1/assets?limit=200")
      .then((d) => setAssets(d.items))
      .finally(() => setLoading(false));
  }, []);

  const filtered = assets.filter((a) => a.asset_id.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Asset Explorer</h2>
      <input
        className="border p-2 mb-4 w-full max-w-md"
        placeholder="Search asset ID"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {loading ? (
        <p>Loading…</p>
      ) : (
        <table className="w-full bg-white shadow rounded">
          <thead>
            <tr className="text-left border-b">
              <th className="p-2">Asset ID</th>
              <th className="p-2">Type</th>
              <th className="p-2">Status</th>
              <th className="p-2">Region</th>
              <th className="p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr key={a.asset_id} className="border-b">
                <td className="p-2">{a.asset_id}</td>
                <td className="p-2">{a.asset_type}</td>
                <td className="p-2">{a.status}</td>
                <td className="p-2">{a.region ?? "—"}</td>
                <td className="p-2">
                  <Link className="text-teal" to={`/risk?asset=${a.asset_id}`}>
                    Risk
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
