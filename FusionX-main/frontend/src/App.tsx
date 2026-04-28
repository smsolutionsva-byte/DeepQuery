import { Activity, Database, FileSearch, ShieldCheck, SlidersHorizontal } from "lucide-react";
import SatelliteMap from "./components/SatelliteMap";
import DataStorageAnimation from "./components/DataStorageAnimation";
import SystemAnalysisAnimation from "./components/SystemAnalysisAnimation";
import AnswerPreparationAnimation from "./components/AnswerPreparationAnimation";
import VectorCreationAnimation from "./components/VectorCreationAnimation";
import { ChangeEvent, useEffect, useMemo, useState } from "react";

const navItems = [
  "Visual Search",
  "Spectral Layers",
  "Patch Database",
  "Search History",
  "Compliance Audit",
];

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.trim() || "http://localhost:8000";

type PatchRecord = {
  id: string;
  lat: number;
  lng: number;
  tag: string;
  confidence: number;
  filePath?: string;
  caption?: string;
};

type AnalyzeTextMatch = {
  id: string;
  file_path: string;
  similarity: number;
  confidence: number;
  lat: number;
  lng: number;
  label: string;
  caption?: string | null;
};

type AnalyzeTextResponse = {
  query: string;
  detected_topic: string;
  detected_task: string;
  dataset_root: string;
  total_matches: number;
  status_message: string;
  matches: AnalyzeTextMatch[];
  reasoning_title: string;
  reasoning: string;
  online_references: OnlineReference[];
  graph_summary: string;
  graphs: GraphArtifact[];
};

type DatasetStatusResponse = {
  total_images: number;
  indexed: boolean;
  sample_paths: string[];
};

type OnlineReference = {
  title: string;
  url: string;
  snippet: string;
};

type GraphArtifact = {
  path: string;
  url: string;
};

type AnalyzeTextJobStartResponse = {
  job_id: string;
  status: string;
  message: string;
};

type AnalyzeTextJobStatusResponse = {
  job_id: string;
  status: string;
  stage: string;
  progress: number;
  message: string;
  current_file?: string | null;
  error?: string | null;
  result?: AnalyzeTextResponse | null;
};

const DEFAULT_PATCHES: PatchRecord[] = [
  { id: "patch-1", lat: -3.4653, lng: -62.2159, tag: "deforestation", confidence: 0.94 },
  { id: "patch-2", lat: 34.0522, lng: -118.2437, tag: "urban pool", confidence: 0.88 },
  { id: "patch-3", lat: 25.2048, lng: 55.2708, tag: "construction", confidence: 0.91 },
  { id: "patch-4", lat: -33.8688, lng: 151.2093, tag: "coastal sediment", confidence: 0.85 },
  { id: "patch-5", lat: 48.8566, lng: 2.3522, tag: "logistics", confidence: 0.92 },
];

export default function App() {
  const [activeNav, setActiveNav] = useState(navItems[0]);
  const [query, setQuery] = useState("");
  const [searchStatus, setSearchStatus] = useState("Idle");
  const [patches, setPatches] = useState<PatchRecord[]>(DEFAULT_PATCHES);
  const [selectedPatchId, setSelectedPatchId] = useState(DEFAULT_PATCHES[0]?.id ?? "");
  const [searchHistory, setSearchHistory] = useState<string[]>([]);
  const [auditLog, setAuditLog] = useState<string[]>(["System initialized"]);
  const [minConfidence, setMinConfidence] = useState(0);
  const [rotateSpeed, setRotateSpeed] = useState(0.45);
  const [showMarkers, setShowMarkers] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isEncoding, setIsEncoding] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeJobId, setActiveJobId] = useState("");
  const [analysisCurrentFile, setAnalysisCurrentFile] = useState("");
  const [uniqueCode, setUniqueCode] = useState("");
  const [vectorPreview, setVectorPreview] = useState<number[]>([]);
  const [encodeMessage, setEncodeMessage] = useState("Upload an image to generate vector code");
  const [reasoningTitle, setReasoningTitle] = useState("Reference Summary");
  const [reasoningText, setReasoningText] = useState("");
  const [onlineReferences, setOnlineReferences] = useState<OnlineReference[]>([]);
  const [graphSummary, setGraphSummary] = useState("");
  const [graphs, setGraphs] = useState<GraphArtifact[]>([]);
  
  // Animation states
  const [showDataStorage, setShowDataStorage] = useState(false);
  const [dataStorageStatus, setDataStorageStatus] = useState<"uploading" | "processing" | "success" | "error">("uploading");
  const [showSystemAnalysis, setShowSystemAnalysis] = useState(false);
  const [analysisStage, setAnalysisStage] = useState<"scanning" | "analyzing" | "computing" | "complete">("scanning");
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [showAnswerPreparation, setShowAnswerPreparation] = useState(false);
  const [answerStage, setAnswerStage] = useState<"thinking" | "generating" | "validating" | "ready">("thinking");
  const [answerProgress, setAnswerProgress] = useState(0);
  const [showVectorCreation, setShowVectorCreation] = useState(false);
  const [vectorStage, setVectorStage] = useState<"encoding" | "vectorizing" | "cosine" | "storing">("encoding");
  const [vectorProgress, setVectorProgress] = useState(0);

  const visiblePatches = useMemo(
    () => patches.filter((p) => p.confidence >= minConfidence),
    [patches, minConfidence],
  );

  const globePoints = useMemo(
    () => (showMarkers ? visiblePatches : []),
    [showMarkers, visiblePatches],
  );

  const selectedPatch = useMemo(
    () => visiblePatches.find((patch) => patch.id === selectedPatchId) ?? null,
    [visiblePatches, selectedPatchId],
  );

  const resolveApiUrl = (resourceUrl: string) => {
    if (!resourceUrl) return "";
    if (resourceUrl.startsWith("http://") || resourceUrl.startsWith("https://")) {
      return resourceUrl;
    }
    const normalized = resourceUrl.startsWith("/") ? resourceUrl : `/${resourceUrl}`;
    return `${API_BASE}${normalized}`;
  };

  const mapSystemStage = (
    stage: string,
  ): "scanning" | "analyzing" | "computing" | "complete" => {
    if (stage === "queued" || stage === "scanning" || stage === "indexing") {
      return "scanning";
    }
    if (stage === "local_search" || stage === "online_search") {
      return "analyzing";
    }
    if (stage === "graphs" || stage === "summarizing") {
      return "computing";
    }
    return "complete";
  };

  const mapAnswerStage = (
    stage: string,
  ): "thinking" | "generating" | "validating" | "ready" => {
    if (stage === "queued" || stage === "scanning" || stage === "indexing") {
      return "thinking";
    }
    if (stage === "local_search" || stage === "online_search") {
      return "generating";
    }
    if (stage === "graphs" || stage === "summarizing") {
      return "validating";
    }
    return "ready";
  };

  useEffect(() => {
    let ignore = false;

    async function loadDatasetStatus() {
      try {
        const res = await fetch(`${API_BASE}/dataset-status`);
        if (!res.ok) {
          throw new Error("Failed to read dataset status.");
        }
        const body = (await res.json()) as DatasetStatusResponse;
        if (ignore) {
          return;
        }
        setSearchStatus(
          `Dataset ready: ${body.total_images} images${body.indexed ? " (index loaded)" : ""}`,
        );
      } catch {
        if (!ignore) {
          setSearchStatus("Backend unavailable. Start FusionX backend on port 8000.");
        }
      }
    }

    loadDatasetStatus();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (visiblePatches.some((patch) => patch.id === selectedPatchId)) {
      return;
    }
    setSelectedPatchId(visiblePatches[0]?.id ?? "");
  }, [visiblePatches, selectedPatchId]);

  async function handleAnalyze() {
    const normalizedQuery = query.trim();
    if (!normalizedQuery || isAnalyzing) return;

    setIsAnalyzing(true);
    setActiveJobId("");
    setAnalysisCurrentFile("");
    setReasoningTitle("Reference Summary");
    setReasoningText("");
    setOnlineReferences([]);
    setGraphSummary("");
    setGraphs([]);
    setMinConfidence(0);

    // Start system analysis animation
    setShowSystemAnalysis(true);
    setAnalysisStage("scanning");
    setAnalysisProgress(2);
    setSearchStatus("Analyzing semantic query...");
    setSearchHistory((prev) => [normalizedQuery, ...prev].slice(0, 10));
    setShowAnswerPreparation(true);
    setAnswerStage("thinking");
    setAnswerProgress(2);

    try {
      const startRes = await fetch(`${API_BASE}/analyze-text/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: normalizedQuery,
          top_k: 8,
        }),
      });

      const startBody = (await startRes.json().catch(() => ({}))) as AnalyzeTextJobStartResponse & {
        detail?: string;
      };

      if (!startRes.ok || !startBody.job_id) {
        throw new Error(startBody.detail || "Failed to start semantic analysis.");
      }
      setActiveJobId(startBody.job_id);

      let finalResult: AnalyzeTextResponse | null = null;
      for (let attempt = 0; attempt < 600; attempt += 1) {
        const statusRes = await fetch(`${API_BASE}/analysis-jobs/${startBody.job_id}`);
        const statusBody = (await statusRes.json().catch(() => ({}))) as AnalyzeTextJobStatusResponse & {
          detail?: string;
        };

        if (!statusRes.ok) {
          throw new Error(statusBody.detail || "Unable to read analysis job status.");
        }

        const stage = statusBody.stage || "queued";
        const progress = Number.isFinite(statusBody.progress) ? statusBody.progress : 0;
        setAnalysisStage(mapSystemStage(stage));
        setAnswerStage(mapAnswerStage(stage));
        setAnalysisProgress(progress);
        setAnswerProgress(progress);
        setSearchStatus(statusBody.message || "Processing...");
        setAnalysisCurrentFile(statusBody.current_file || "");

        if (statusBody.status === "failed") {
          throw new Error(statusBody.error || statusBody.message || "Analysis failed.");
        }
        if (statusBody.status === "completed" && statusBody.result) {
          finalResult = statusBody.result;
          break;
        }

        await new Promise((resolve) => setTimeout(resolve, attempt < 300 ? 900 : 2000));
      }

      if (!finalResult) {
        throw new Error(
          "Analysis timed out after waiting for backend completion. The backend may still be processing a large dataset."
        );
      }

      const nextPatches: PatchRecord[] = (Array.isArray(finalResult.matches) ? finalResult.matches : []).map((item, idx) => ({
        id: item.id || `patch-${idx + 1}`,
        lat: Number.isFinite(item.lat) ? item.lat : 0,
        lng: Number.isFinite(item.lng) ? item.lng : 0,
        tag: item.label || item.file_path.split(/[\\/]/).pop() || `match-${idx + 1}`,
        confidence: Number.isFinite(item.confidence) ? item.confidence : item.similarity ?? 0,
        filePath: item.file_path,
        caption: item.caption || undefined,
      }));

      setPatches(nextPatches);
      setSelectedPatchId(nextPatches[0]?.id ?? "");
      setReasoningTitle(finalResult.reasoning_title || "Reference Summary");
      setReasoningText(finalResult.reasoning || "");
      setOnlineReferences(Array.isArray(finalResult.online_references) ? finalResult.online_references : []);
      setGraphSummary(finalResult.graph_summary || "");
      setGraphs(Array.isArray(finalResult.graphs) ? finalResult.graphs : []);
      setSearchStatus(finalResult.status_message || `Found ${nextPatches.length} local matches.`);
      setAuditLog((prev) => [
        `Query analyzed (${finalResult.detected_topic}/${finalResult.detected_task}): ${normalizedQuery}`,
        ...prev,
      ].slice(0, 20));

      // Complete analysis
      setAnalysisStage("complete");
      setAnalysisProgress(100);
      setAnswerStage("ready");
      setAnswerProgress(100);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Semantic analysis failed.";
      setSearchStatus(message);
      setAuditLog((prev) => [`Query failed: ${normalizedQuery}`, ...prev].slice(0, 20));
      setAnalysisStage("complete");
      setAnalysisProgress(100);
      setAnswerStage("ready");
      setAnswerProgress(100);
    } finally {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setShowSystemAnalysis(false);
      setShowAnswerPreparation(false);
      setActiveJobId("");
      setIsAnalyzing(false);
    }
  }

  async function handleEncode() {
    if (!selectedFile) return;
    
    // Start vector creation animation
    setShowVectorCreation(true);
    setVectorStage("encoding");
    setVectorProgress(0);
    
    // Start data storage animation
    setShowDataStorage(true);
    setDataStorageStatus("uploading");
    
    const formData = new FormData();
    formData.append("file", selectedFile);
    setIsEncoding(true);
    setEncodeMessage("Encoding image...");
    
    try {
      // Simulate encoding phase
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setVectorStage("vectorizing");
      setVectorProgress(25);
      setDataStorageStatus("processing");
      
      const res = await fetch(`${API_BASE}/encode-image`, {
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) {
        throw new Error("Unable to encode image");
      }
      
      // Simulate vectorizing phase
      await new Promise((resolve) => setTimeout(resolve, 1200));
      setVectorStage("cosine");
      setVectorProgress(60);
      
      const body = await res.json();
      const vectorData = Array.isArray(body.vector_preview) ? body.vector_preview : [];
      
      // Simulate cosine computation
      await new Promise((resolve) => setTimeout(resolve, 800));
      setVectorStage("storing");
      setVectorProgress(85);
      
      // Simulate storing
      await new Promise((resolve) => setTimeout(resolve, 600));
      setVectorProgress(100);
      setDataStorageStatus("success");
      
      setUniqueCode(body.unique_math_code ?? "");
      setVectorPreview(vectorData);
      setEncodeMessage(`Encoded ${body.embedding_dim ?? 0} dimensions`);
      setAuditLog((prev) => [`Image encoded: ${body.unique_math_code ?? "unknown"}`, ...prev].slice(0, 20));
      
      // Hide animations after completion
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setShowVectorCreation(false);
      setShowDataStorage(false);
      
    } catch {
      setDataStorageStatus("error");
      setEncodeMessage("Encoding failed. Check backend is running on port 8000.");
      setAuditLog((prev) => ["Image encoding failed", ...prev].slice(0, 20));
      
      // Hide animations after error
      await new Promise((resolve) => setTimeout(resolve, 2000));
      setShowVectorCreation(false);
      setShowDataStorage(false);
    } finally {
      setIsEncoding(false);
    }
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(e.target.files?.[0] ?? null);
    setUniqueCode("");
    setVectorPreview([]);
  }

  function renderOperationsPanel() {
    if (activeNav === "Spectral Layers") {
      return (
        <section className="mode-panel">
          <h3>Spectral Layers</h3>
          <label>
            Minimum confidence: {minConfidence.toFixed(2)}
            <input
              type="range"
              min={0}
              max={0.99}
              step={0.01}
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
            />
          </label>
          <label>
            Globe rotate speed: {rotateSpeed.toFixed(2)}
            <input
              type="range"
              min={0}
              max={1.2}
              step={0.05}
              value={rotateSpeed}
              onChange={(e) => setRotateSpeed(Number(e.target.value))}
            />
          </label>
          <label className="toggle-row">
            <input type="checkbox" checked={showMarkers} onChange={(e) => setShowMarkers(e.target.checked)} />
            Show semantic markers
          </label>
        </section>
      );
    }
    if (activeNav === "Patch Database") {
      return (
        <section className="mode-panel">
          <h3>Patch Database</h3>
          <ul className="list">
            {visiblePatches.length === 0 && <li>No dataset matches yet.</li>}
            {visiblePatches.map((p) => (
              <li key={p.id}>
                <button type="button" onClick={() => setSelectedPatchId(p.id)} className={selectedPatchId === p.id ? "selected" : ""}>
                  {p.id} | {p.tag} | {p.confidence.toFixed(2)}
                </button>
              </li>
            ))}
          </ul>
        </section>
      );
    }
    if (activeNav === "Search History") {
      return (
        <section className="mode-panel">
          <h3>Search History</h3>
          <ul className="list">
            {searchHistory.length === 0 && <li>No searches yet.</li>}
            {searchHistory.map((item, idx) => (
              <li key={`${item}-${idx}`}>
                <button type="button" onClick={() => setQuery(item)}>
                  {item}
                </button>
              </li>
            ))}
          </ul>
        </section>
      );
    }
    if (activeNav === "Compliance Audit") {
      return (
        <section className="mode-panel">
          <h3>Compliance Audit</h3>
          <ul className="list">
            {auditLog.map((item, idx) => (
              <li key={`${item}-${idx}`}>{item}</li>
            ))}
          </ul>
        </section>
      );
    }
    return (
      <section className="mode-panel">
        <h3>Visual Search</h3>
        <p>{searchStatus}</p>
        {activeJobId && <p>Job: {activeJobId}</p>}
        {analysisCurrentFile && <p className="path-line">Processing: {analysisCurrentFile}</p>}
        <p>Selected patch: {selectedPatchId || "None"}</p>
        {selectedPatch?.filePath && <p>{selectedPatch.filePath}</p>}
        {selectedPatch?.caption && <p>{selectedPatch.caption}</p>}
      </section>
    );
  }

  return (
    <div className="screen">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">&gt;</div>
          <div>
            <div className="brand-title">TERRASEMANTIC</div>
            <div className="brand-subtitle">GEOSPATIAL INTELLIGENCE</div>
          </div>
        </div>

        <div className="nav-title">NAVIGATION</div>
        <nav className="nav-list">
          {navItems.map((item, idx) => (
            <button
              key={item}
              className={`nav-item ${activeNav === item ? "active" : ""}`}
              type="button"
              onClick={() => setActiveNav(item)}
            >
              {idx === 0 && <FileSearch size={14} />}
              {idx === 1 && <SlidersHorizontal size={14} />}
              {idx === 2 && <Database size={14} />}
              {idx === 3 && <Activity size={14} />}
              {idx === 4 && <ShieldCheck size={14} />}
              <span>{item}</span>
            </button>
          ))}
        </nav>

        <div className="system-card">
          <div className="sys-title">SYSTEM RESOURCES</div>
          <div className="sys-row">
            <span>VECTOR INDEX</span>
            <span>84%</span>
          </div>
          <div className="bar">
            <div className="bar-fill vector" />
          </div>
          <div className="sys-row">
            <span>GPU COMPUTE</span>
            <span>32%</span>
          </div>
          <div className="bar">
            <div className="bar-fill gpu" />
          </div>
        </div>

        <div className="user-chip">
          <div className="avatar" />
          <div>
            <div className="user-name">Mahesh Aruna</div>
            <div className="user-role">LEAD ARCHITECT</div>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="top-center">
          <h1>TerraSemantic</h1>
          <div className="search-shell">
            <input
              placeholder="Search pattern (e.g. 'illegal mining near river')"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="button" onClick={handleAnalyze} disabled={isAnalyzing}>
              {isAnalyzing ? "Analyzing..." : "Analyze"}
            </button>
          </div>
          <div className="index-pill">GLOBAL SEMANTIC INDEX ACTIVE</div>
        </header>

        <section className="stage">
          <div className="starfield" />
          <div className="orbit-ring ring-a" />
          <div className="orbit-ring ring-b" />
          <div className="marker marker-a" />
          <div className="marker marker-b" />
          <div className="marker marker-c" />
          <SatelliteMap
            points={globePoints}
            autoRotateSpeed={rotateSpeed}
            highlightedPointId={selectedPatchId}
            onPointSelect={setSelectedPatchId}
          />
          <button type="button" className="preview-btn">
            Preview
          </button>
        </section>

        <aside className="right-status">
          <div className="status-chip">
            <span>ENGINE STATE</span>
            <strong>HNSW Index Active</strong>
          </div>
          <div className="status-chip">
            <span>PROJECTION</span>
            <strong>SPHERICAL</strong>
          </div>
        </aside>

        <section className="insights">
          <div className="insights-title">LIVE INSIGHTS</div>
          <p>{searchStatus === "Idle" ? "Scanning global vector space. Rotate to explore clusters." : searchStatus}</p>
          {analysisCurrentFile && <p className="path-line">Now processing: {analysisCurrentFile}</p>}
        </section>
        <section className="encode-panel">
          <div className="insights-title">IMAGE TO VECTOR</div>
          <input type="file" accept="image/*" onChange={handleFileChange} />
          <button type="button" onClick={handleEncode} disabled={!selectedFile || isEncoding}>
            {isEncoding ? "Encoding..." : "Convert"}
          </button>
          <p className="encode-msg">{encodeMessage}</p>
          {uniqueCode && <p className="code-line">Code: {uniqueCode}</p>}
          {vectorPreview.length > 0 && (
            <p className="vector-line">v[0..11]: {vectorPreview.map((v) => v.toFixed(4)).join(", ")}</p>
          )}
        </section>
        {(reasoningText || onlineReferences.length > 0 || graphs.length > 0) && (
          <section className="analysis-results">
            <article className="result-box">
              <h3>{reasoningTitle || "Summary"}</h3>
              <p>{reasoningText || "No summary generated."}</p>
            </article>

            <article className="result-box">
              <h3>References</h3>
              {onlineReferences.length === 0 && <p>No online references returned.</p>}
              <ul className="result-list">
                {onlineReferences.map((item, idx) => (
                  <li key={`${item.url}-${idx}`}>
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.title || item.url}
                    </a>
                    {item.snippet && <p>{item.snippet}</p>}
                  </li>
                ))}
              </ul>
            </article>

            <article className="result-box">
              <h3>Graphs</h3>
              {graphSummary && <p>{graphSummary}</p>}
              {graphs.length === 0 && <p>No graph outputs available yet.</p>}
              <div className="graph-grid">
                {graphs.map((graph, idx) => (
                  <a
                    key={`${graph.path}-${idx}`}
                    href={resolveApiUrl(graph.url)}
                    target="_blank"
                    rel="noreferrer"
                    className="graph-thumb"
                  >
                    <img src={resolveApiUrl(graph.url)} alt={`Graph ${idx + 1}`} loading="lazy" />
                  </a>
                ))}
              </div>
            </article>
          </section>
        )}
        {renderOperationsPanel()}

        <footer className="footer-bar">
          <span>SEMANTIC ENGINE v2.4</span>
          <span>Index: {visiblePatches.length} Qualified Tiles | SigLIP-B/16</span>
          <span>PATCH: {selectedPatchId || "None"}</span>
          <span>MODE: {activeNav}</span>
        </footer>
      </main>
      
      {/* Animation Components */}
      <DataStorageAnimation 
        isActive={showDataStorage}
        status={dataStorageStatus}
        message={dataStorageStatus === "uploading" ? "Uploading data to backend..." : 
                dataStorageStatus === "processing" ? "Processing vector embeddings..." :
                dataStorageStatus === "success" ? "Data successfully stored!" :
                "Failed to store data"}
      />
      
      <SystemAnalysisAnimation 
        isActive={showSystemAnalysis}
        stage={analysisStage}
        progress={analysisProgress}
        message={analysisCurrentFile
          ? `Processing: ${analysisCurrentFile}`
          : analysisStage === "scanning" ? "Scanning vector space for patterns..." :
            analysisStage === "analyzing" ? "Analyzing semantic relationships..." :
            analysisStage === "computing" ? "Computing similarity scores..." :
            "Analysis complete!"
        }
      />
      
      <AnswerPreparationAnimation 
        isActive={showAnswerPreparation}
        stage={answerStage}
        progress={answerProgress}
        message={searchStatus}
      />
      
      <VectorCreationAnimation 
        isActive={showVectorCreation}
        stage={vectorStage}
        vectorData={vectorPreview}
        progress={vectorProgress}
        message={vectorStage === "encoding" ? "Encoding input data to vectors..." :
                vectorStage === "vectorizing" ? "Creating vector embeddings..." :
                vectorStage === "cosine" ? "Computing cosine similarity..." :
                "Storing in vector database..."}
      />
    </div>
  );
}
