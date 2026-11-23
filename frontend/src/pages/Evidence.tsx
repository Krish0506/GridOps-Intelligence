import { useState } from "react";
import { apiPost } from "../lib/api";

interface Citation { chunk_id: string; document_id: string | null; title: string | null; page_number: number | null; excerpt: string | null; }
interface AskResult { answer: string; citations: Citation[]; evidence_sufficient: boolean; confidence: string; limitations: string[]; }

export default function Evidence() {
  const [question, setQuestion] = useState("");
  const [assetId, setAssetId] = useState("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function ask() {
    setLoading(true);
    try {
      const r = await apiPost<AskResult>("/api/v1/knowledge/ask", { question, asset_id: assetId || null, top_k: 5 });
      setResult(r);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Evidence Intelligence</h2>
      <div className="bg-white p-4 rounded shadow mb-4">
        <input className="border p-2 w-full mb-2" placeholder="Engineering question" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <input className="border p-2 w-full mb-2" placeholder="Asset ID (optional)" value={assetId} onChange={(e) => setAssetId(e.target.value)} />
        <button className="bg-teal text-white px-4 py-2 rounded" onClick={ask} disabled={loading}>
          {loading ? "Asking…" : "Ask"}
        </button>
      </div>
      {result && (
        <div className="bg-white p-4 rounded shadow">
          <p className="font-bold">Answer</p>
          <p className="mb-2">{result.answer}</p>
          <p className="text-sm text-slate-500">Evidence sufficient: {String(result.evidence_sufficient)} · Confidence: {result.confidence}</p>
          <p className="font-bold mt-2">Citations</p>
          <ul className="list-disc ml-6">
            {result.citations.map((c) => (
              <li key={c.chunk_id}>{c.title} (p.{c.page_number ?? "n/a"}) — {c.excerpt}</li>
            ))}
          </ul>
          <p className="font-bold mt-2">Limitations</p>
          <ul className="list-disc ml-6">{result.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
