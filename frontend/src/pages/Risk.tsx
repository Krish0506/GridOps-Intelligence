import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiGet } from "../lib/api";

export default function Risk() {
  const [params] = useSearchParams();
  const asset = params.get("asset");
  const [data, setData] = useState<unknown>(null);

  useEffect(() => {
    if (asset) {
      apiGet(`/api/v1/assets/${asset}`).then(setData).catch(() => setData(null));
    }
  }, [asset]);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Risk Prioritization</h2>
      {asset ? (
        <div className="bg-white p-4 rounded shadow">
          <p className="font-bold">{asset}</p>
          <pre className="text-xs mt-2">{JSON.stringify(data, null, 2)}</pre>
          <p className="text-sm text-slate-500 mt-2">
            Anomaly scores and model probabilities are separate concepts. See Governance for audit history.
          </p>
        </div>
      ) : (
        <p>Select an asset from the Asset Explorer.</p>
      )}
    </div>
  );
}
