from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    scene_urls: List[str] = Field(default_factory=list)
    source: str = "sentinel-2"
    run_fmask: bool = True


class SceneMetadata(BaseModel):
    id: str
    source: str
    timestamp: str
    bbox: List[float]
    cloud_coverage: Optional[float] = None
    confidence: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)


class IndexDocument(BaseModel):
    metadata: SceneMetadata
    image_path: str
    embedding: List[float]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    min_similarity: float = 0.85
    time_from: Optional[str] = None
    time_to: Optional[str] = None


class SearchResult(BaseModel):
    id: str
    similarity: float
    bbox: List[float]
    timestamp: str
    confidence: float
    thumbnail_path: str


class VQARequest(BaseModel):
    question: str
    image_id: str


class VQAResponse(BaseModel):
    image_id: str
    question: str
    answer: str
    confidence: float


class AnalyzeTextRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)


class DatasetMatch(BaseModel):
    id: str
    file_path: str
    similarity: float
    confidence: float
    lat: float
    lng: float
    label: str
    caption: Optional[str] = None


class OnlineReference(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""


class GraphArtifact(BaseModel):
    path: str
    url: str


class AnalyzeTextResponse(BaseModel):
    query: str
    detected_topic: str
    detected_task: str
    dataset_root: str
    total_matches: int
    matches: List[DatasetMatch] = Field(default_factory=list)
    status_message: str
    reasoning_title: str = "Reference Summary"
    reasoning: str = ""
    online_references: List[OnlineReference] = Field(default_factory=list)
    graph_summary: str = ""
    graphs: List[GraphArtifact] = Field(default_factory=list)


class EncodeImageResponse(BaseModel):
    unique_math_code: str
    embedding_dim: int
    vector_preview: List[float] = Field(default_factory=list)


class DatasetStatusResponse(BaseModel):
    dataset_root: str
    total_images: int
    sample_paths: List[str] = Field(default_factory=list)
    indexed: bool = False


class AnalyzeTextJobStartResponse(BaseModel):
    job_id: str
    status: str
    message: str


class AnalyzeTextJobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int = Field(default=0, ge=0, le=100)
    message: str
    current_file: Optional[str] = None
    error: Optional[str] = None
    result: Optional[AnalyzeTextResponse] = None
