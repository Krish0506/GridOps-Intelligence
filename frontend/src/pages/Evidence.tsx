import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { IconDecision, IconEvidence, IconInfo, IconRefresh, IconSearch } from "../components/Icons";
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
  PageHeader,
  SearchField,
  Spinner,
  StatCard,
} from "../components/ui";
import { apiPost } from "../lib/api";
import { useApi } from "../lib/useApi";
import type {
  AskResponse,
  KnowledgeDocument,
  KnowledgeDocumentContent,
  KnowledgeStats,
} from "../lib/types";
import { formatNumber, titleCase, truncate } from "../lib/format";

const SUGGESTIONS = [
  "How many transformers are in the inventory?",
  "How many active work orders are there?",
  "How many failures are recorded and how severe are they?",
  "What does the circuit breaker maintenance guidance recommend?",
  "Summarize the transformer oil analysis guidance.",
  "What is the inspection coverage across assets?",
];

export default function Evidence() {
  const [params] = useSearchParams();
  const initialAsset = params.get("asset") ?? "";
  const [question, setQuestion] = useState(SUGGESTIONS[0]);
  const [assetId, setAssetId] = useState(initialAsset);
  const [category, setCategory] = useState("");
  const [equipment, setEquipment] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);

  const [docSearch, setDocSearch] = useState("");
  const [debouncedDocSearch, setDebouncedDocSearch] = useState("");
  const [docCategory, setDocCategory] = useState("");
  const [docEquipment, setDocEquipment] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedDocSearch(docSearch.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [docSearch]);

  useEffect(() => {
    setAssetId(initialAsset);
  }, [initialAsset]);

  const stats = useApi<KnowledgeStats>("/api/v1/knowledge/stats");
  const documentQuery = useMemo(() => {
    const search = new URLSearchParams();
    if (debouncedDocSearch) search.set("search", debouncedDocSearch);
    if (docCategory) search.set("category", docCategory);
    if (docEquipment) search.set("equipment", docEquipment);
    const suffix = search.toString();
    return `/api/v1/knowledge/documents${suffix ? `?${suffix}` : ""}`;
  }, [debouncedDocSearch, docCategory, docEquipment]);
  const documents = useApi<KnowledgeDocument[]>(documentQuery);
  const documentContent = useApi<KnowledgeDocumentContent>(
    selectedDocument ? `/api/v1/knowledge/documents/${selectedDocument}/content` : null,
  );

  async function ask(prompt?: string) {
    const finalQuestion = (prompt ?? question).trim();
    if (!finalQuestion) return;
    setQuestion(finalQuestion);
    setAsking(true);
    setAskError(null);
    try {
      const response = await apiPost<AskResponse>("/api/v1/knowledge/ask", {
        question: finalQuestion,
        asset_id: assetId.trim() || null,
        top_k: 5,
        category: category || null,
        equipment: equipment || null,
      });
      setResult(response);
    } catch (cause) {
      setAskError(cause instanceof Error ? cause.message : "The question could not be answered.");
      setResult(null);
    } finally {
      setAsking(false);
    }
  }

  const docs = documents.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Evidence & action"
        title="Evidence Intelligence"
        description="Ask engineering questions against the synthetic corpus. Structured count and status questions are routed to PostgreSQL; document questions use hybrid retrieval with citations."
        actions={
          <>
            <Badge tone="teal">{formatNumber(stats.data?.documents)} documents</Badge>
            <Badge tone="slate">{formatNumber(stats.data?.chunks)} indexed chunks</Badge>
            <button className="btn-ghost" type="button" onClick={() => { stats.reload(); documents.reload(); }}>
              <IconRefresh className="h-4 w-4" /> Refresh
            </button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Knowledge documents" value={formatNumber(stats.data?.documents)} hint={`${stats.data?.categories.length ?? 0} categories`} icon={<IconEvidence className="h-5 w-5" />} />
        <StatCard label="Indexed chunks" value={formatNumber(stats.data?.chunks)} hint="Deterministic mock embeddings" tone="blue" />
        <StatCard label="Formats" value={stats.data?.formats.length ?? "—"} hint={stats.data?.formats.map((item) => item.mime_type?.split("/").pop()).join(" · ")} tone="amber" />
        <StatCard
          label="Latest ingestion"
          value={stats.data?.latest_ingestion?.documents_processed ?? "—"}
          hint={stats.data?.latest_ingestion ? `${stats.data.latest_ingestion.chunks_created} chunks · ${stats.data.latest_ingestion.error_count} errors` : "No run recorded"}
          tone="green"
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="Ask a grounded question" subtitle="The answer is limited to retrieved evidence or structured database facts" bodyClassName="p-5">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Asset context (optional)">
                <input className="input" value={assetId} onChange={(event) => setAssetId(event.target.value.toUpperCase())} placeholder="CB-00348" />
              </Field>
              <Field label="Document category">
                <select className="input" value={category} onChange={(event) => setCategory(event.target.value)}>
                  <option value="">All categories</option>
                  {stats.data?.categories.map((item) => (
                    <option key={item.category} value={item.category}>{item.category}</option>
                  ))}
                </select>
              </Field>
              <Field label="Equipment filter">
                <select className="input" value={equipment} onChange={(event) => setEquipment(event.target.value)}>
                  <option value="">All equipment</option>
                  {stats.data?.equipment.map((item) => (
                    <option key={item.equipment} value={item.equipment}>{titleCase(item.equipment)}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="mt-3">
              <Field label="Question">
                <textarea
                  className="input min-h-[92px]"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Ask about inventory counts, maintenance guidance, inspection practice, or a specific asset."
                />
              </Field>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="rounded-full border border-ink-300 bg-white px-3 py-1.5 text-[11px] font-medium text-ink-600 transition hover:border-teal-500 hover:text-teal-700"
                  onClick={() => ask(suggestion)}
                >
                  {truncate(suggestion, 52)}
                </button>
              ))}
            </div>
            <button type="button" className="btn-accent mt-4" onClick={() => ask()} disabled={asking || !question.trim()}>
              {asking ? <Spinner /> : <IconSearch className="h-4 w-4" />}
              {asking ? "Retrieving evidence…" : "Ask evidence"}
            </button>
          </Card>

          {askError && <ErrorBlock message={askError} onRetry={() => ask()} />}

          {result && (
            <Card
              title="Answer"
              subtitle={
                <span className="flex flex-wrap items-center gap-2">
                  <Badge tone={result.route === "structured_database" ? "blue" : "teal"}>
                    {result.route === "structured_database" ? "Structured database" : "Document retrieval"}
                  </Badge>
                  <Badge tone={result.evidence_sufficient ? "green" : "amber"}>
                    {result.evidence_sufficient ? "Evidence sufficient" : "Insufficient evidence"}
                  </Badge>
                  <Badge tone="slate">{result.confidence} confidence</Badge>
                </span>
              }
              bodyClassName="p-5"
            >
              <p className="text-sm leading-7 text-ink-700">{result.answer}</p>

              {result.structured_data && Object.keys(result.structured_data.breakdown).length > 0 && (
                <div className="mt-4 rounded-xl border border-ink-300/60 bg-ink-50 px-4 py-3">
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-500">Structured breakdown</p>
                  <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {Object.entries(result.structured_data.breakdown).map(([key, value]) => (
                      <KeyValue key={key} label={titleCase(key)}>
                        {typeof value === "number" ? formatNumber(value) : String(value)}
                      </KeyValue>
                    ))}
                  </dl>
                </div>
              )}

              {result.citations.length > 0 && (
                <div className="mt-5">
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-500">Citations</p>
                  <ol className="space-y-2">
                    {result.citations.map((citation, index) => (
                      <li key={`${citation.chunk_id}-${index}`} className="rounded-xl border border-ink-300/60 px-4 py-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-semibold text-ink-900">
                            [{index + 1}] {citation.title ?? citation.document_id ?? "Untitled document"}
                          </p>
                          <span className="text-[10px] text-ink-500">
                            {citation.revision ?? "Revision unknown"} · page {citation.page_number ?? "n/a"}
                          </span>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-ink-500">{citation.excerpt}</p>
                        <p className="mt-1 font-mono text-[10px] text-ink-500">{citation.document_id} · checksum {citation.source_checksum?.slice(0, 12)}</p>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {result.key_facts.length > 0 && result.route === "document_retrieval" && (
                <details className="mt-4 rounded-xl bg-ink-50 px-4 py-3">
                  <summary className="cursor-pointer text-[11px] font-semibold text-ink-600">Supporting passages</summary>
                  <ul className="mt-2 space-y-2 text-[11px] leading-5 text-ink-500">
                    {result.key_facts.slice(0, 5).map((fact, index) => (
                      <li key={`${index}-${fact.slice(0, 20)}`}>{truncate(fact, 320)}</li>
                    ))}
                  </ul>
                </details>
              )}

              <div className="mt-4">
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-500">Limitations</p>
                <ul className="space-y-1 text-[11px] leading-5 text-ink-500">
                  {result.limitations.map((limitation) => (
                    <li key={limitation} className="flex gap-2"><IconInfo className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />{limitation}</li>
                  ))}
                </ul>
              </div>

              {result.asset_id && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <a className="btn-ghost" href={`/risk?asset=${result.asset_id}`}><IconDecision className="h-4 w-4" /> Open asset risk</a>
                  <a className="btn-ghost" href={`/decisions?asset=${result.asset_id}`}>Create decision</a>
                </div>
              )}
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card title="Corpus" subtitle="Browse and open source documents" bodyClassName="p-0">
            <div className="space-y-2 border-b border-ink-300/50 px-4 py-3">
              <SearchField value={docSearch} onChange={setDocSearch} placeholder="Search titles or extracted text" />
              <div className="grid grid-cols-2 gap-2">
                <select className="input py-2 text-xs" value={docCategory} onChange={(event) => setDocCategory(event.target.value)}>
                  <option value="">All categories</option>
                  {stats.data?.categories.map((item) => (
                    <option key={item.category} value={item.category}>{item.category}</option>
                  ))}
                </select>
                <select className="input py-2 text-xs" value={docEquipment} onChange={(event) => setDocEquipment(event.target.value)}>
                  <option value="">All equipment</option>
                  {stats.data?.equipment.map((item) => (
                    <option key={item.equipment} value={item.equipment}>{titleCase(item.equipment)}</option>
                  ))}
                </select>
              </div>
            </div>
            {documents.error ? (
              <div className="p-4"><ErrorBlock message={documents.error} onRetry={documents.reload} /></div>
            ) : documents.loading && !documents.data ? (
              <div className="p-4"><LoadingBlock rows={5} /></div>
            ) : docs.length === 0 ? (
              <div className="p-4"><EmptyBlock title="No documents match" /></div>
            ) : (
              <ul className="max-h-[520px] divide-y divide-ink-300/50 overflow-y-auto">
                {docs.map((document) => (
                  <li key={document.document_id}>
                    <button
                      type="button"
                      className="w-full px-4 py-3 text-left transition hover:bg-teal-50/40"
                      onClick={() => setSelectedDocument(document.document_id)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-semibold text-ink-900">{document.title}</p>
                        <Badge tone="slate">{document.mime_type?.split(".").pop()?.toUpperCase() ?? "FILE"}</Badge>
                      </div>
                      <p className="mt-0.5 text-[10px] text-ink-500">
                        {document.document_id} · {document.category} · {document.revision}
                      </p>
                      <p className="mt-0.5 text-[10px] text-ink-500">
                        Equipment: {document.equipment_applicability ?? "unspecified"} · {document.chunk_count} chunk{document.chunk_count === 1 ? "" : "s"}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Callout tone="amber" title="Synthetic corpus">
            These documents are synthetic demonstrations written for this project. They are not official engineering standards, manufacturer instructions, or
            regulatory guidance. Retrieval is hybrid semantic/keyword search with deterministic mock embeddings.
          </Callout>

          {stats.data?.latest_ingestion && (
            <Card title="Latest ingestion run" bodyClassName="p-5">
              <dl className="grid grid-cols-2 gap-4">
                <KeyValue label="Status">{stats.data.latest_ingestion.status}</KeyValue>
                <KeyValue label="Documents">{formatNumber(stats.data.latest_ingestion.documents_processed)}</KeyValue>
                <KeyValue label="Chunks">{formatNumber(stats.data.latest_ingestion.chunks_created)}</KeyValue>
                <KeyValue label="Errors">{formatNumber(stats.data.latest_ingestion.error_count)}</KeyValue>
              </dl>
            </Card>
          )}
        </div>
      </div>

      <Drawer
        open={Boolean(selectedDocument)}
        onClose={() => setSelectedDocument(null)}
        title={documentContent.data?.title ?? selectedDocument ?? "Document"}
        subtitle={documentContent.data ? `${documentContent.data.document_id} · ${documentContent.data.category} · ${documentContent.data.revision}` : "Loading document…"}
        width="max-w-3xl"
      >
        {documentContent.error ? (
          <ErrorBlock message={documentContent.error} onRetry={documentContent.reload} />
        ) : documentContent.loading || !documentContent.data ? (
          <LoadingBlock rows={8} />
        ) : (
          <div className="space-y-5">
            <dl className="grid grid-cols-2 gap-4">
              <KeyValue label="Category">{documentContent.data.category}</KeyValue>
              <KeyValue label="Equipment">{titleCase(documentContent.data.equipment_applicability)}</KeyValue>
              <KeyValue label="Revision">{documentContent.data.revision}</KeyValue>
              <KeyValue label="Publication date">{documentContent.data.publication_date ?? "—"}</KeyValue>
              <KeyValue label="Source file">{documentContent.data.source_filename}</KeyValue>
              <KeyValue label="Chunks">{documentContent.data.chunks.length}</KeyValue>
            </dl>
            <div>
              <p className="label">Extracted text</p>
              <div className="max-h-[420px] overflow-y-auto whitespace-pre-wrap rounded-xl border border-ink-300/60 bg-ink-50 px-4 py-3 text-xs leading-6 text-ink-700">
                {documentContent.data.extracted_text}
              </div>
            </div>
            <div>
              <p className="label">Indexed chunks</p>
              <ul className="space-y-2">
                {documentContent.data.chunks.map((chunk) => (
                  <li key={chunk.chunk_id} className="rounded-xl border border-ink-300/60 px-4 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-semibold text-ink-700">Chunk {chunk.chunk_id.slice(0, 12)}</span>
                      <span className="text-[10px] text-ink-500">page {chunk.page_number ?? "n/a"}</span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-ink-500">{truncate(chunk.text, 360)}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Drawer>
    </>
  );
}
