import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";

interface Decision { decision_id: string; asset_id: string; decision_status: string; decision_reason: string | null; }

export default function Decisions() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<{ items: Decision[]; total: number }>("/api/v1/decisions?limit=50")
      .then((d) => setDecisions(d.items))
      .finally(() => setLoading(false));
  }, []);

  async function approve(id: string) {
    const reason = prompt("Reason for approval:");
    if (!reason) return;
    await apiPost(`/api/v1/decisions/${id}/approve`, { reviewer: "demo-reviewer", reason });
    const d = await apiGet<{ items: Decision[]; total: number }>("/api/v1/decisions?limit=50");
    setDecisions(d.items);
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Engineering Decision Review</h2>
      {loading ? (
        <p>Loading…</p>
      ) : (
        <table className="w-full bg-white shadow rounded">
          <thead>
            <tr className="text-left border-b">
              <th className="p-2">Decision ID</th>
              <th className="p-2">Asset</th>
              <th className="p-2">Status</th>
              <th className="p-2">Reason</th>
              <th className="p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((d) => (
              <tr key={d.decision_id} className="border-b">
                <td className="p-2 text-xs">{d.decision_id}</td>
                <td className="p-2">{d.asset_id}</td>
                <td className="p-2">{d.decision_status}</td>
                <td className="p-2">{d.decision_reason ?? "—"}</td>
                <td className="p-2">
                  {d.decision_status === "IN_REVIEW" && (
                    <button className="text-teal" onClick={() => approve(d.decision_id)}>
                      Approve
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="text-sm text-slate-500 mt-2">
        Decisions are human-in-the-loop. The system never auto-approves.
      </p>
    </div>
  );
}
