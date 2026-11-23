import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";

export default function Governance() {
  const [runs, setRuns] = useState<unknown[]>([]);
  const [docs, setDocs] = useState<unknown[]>([]);

  useEffect(() => {
    apiGet<{ items: unknown[] }>("/api/v1/ingestion/runs?limit=20").then((d) => setRuns(d.items)).catch(() => {});
    apiGet<unknown[]>("/api/v1/knowledge/documents").then(setDocs).catch(() => {});
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Governance and Audit</h2>
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded shadow">
          <p className="font-bold mb-2">Ingestion Runs</p>
          <p>{runs.length} recent runs</p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <p className="font-bold mb-2">Knowledge Documents</p>
          <p>{docs.length} documents</p>
        </div>
      </div>
      <p className="text-sm text-slate-500 mt-4">
        Synthetic data only. Model monitoring and drift detection are not implemented.
      </p>
    </div>
  );
}
