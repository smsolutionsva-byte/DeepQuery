from __future__ import annotations

import hashlib
import importlib
import io
import os
import sys
import threading
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

from app.models.schemas import (
    AnalyzeTextJobStartResponse,
    AnalyzeTextJobStatusResponse,
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    DatasetMatch,
    DatasetStatusResponse,
    EncodeImageResponse,
    GraphArtifact,
    OnlineReference,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_DIR = REPO_ROOT / "project"
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_SYSTEM_LOCK = threading.Lock()
_JOB_LOCK = threading.Lock()
_ANALYSIS_JOBS: dict[str, dict[str, Any]] = {}
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _ensure_project_path() -> None:
    project_path = str(PROJECT_DIR)
    if project_path not in sys.path:
        sys.path.insert(0, project_path)


@lru_cache(maxsize=1)
def _project_api() -> dict[str, Any]:
    _ensure_project_path()
    project_main = importlib.import_module("main")
    file_loader = importlib.import_module("utils.file_loader")
    return {
        "system_cls": getattr(project_main, "SatelliteImageIntelligenceSystem"),
        "dataset_error": getattr(file_loader, "DatasetNotFoundError"),
        "discover_images": getattr(file_loader, "discover_images"),
        "dataset_preview_paths": getattr(file_loader, "dataset_preview_paths"),
    }


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_system() -> Any:
    api = _project_api()
    system_cls = api["system_cls"]
    return system_cls(
        project_root=PROJECT_DIR,
        offline_processing=False,
        fast_mode=_env_flag("SATINT_FAST_MODE", default=False),
    )


def _stable_geo_from_text(value: str) -> tuple[float, float]:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    lat_raw = int(digest[:8], 16) / 0xFFFFFFFF
    lng_raw = int(digest[8:16], 16) / 0xFFFFFFFF
    lat = round((lat_raw * 170.0) - 85.0, 6)
    lng = round((lng_raw * 360.0) - 180.0, 6)
    return lat, lng


def _output_file_url(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(OUTPUT_DIR.resolve())
    except Exception:
        return ""
    return f"/output-files/{relative.as_posix()}"


def _to_references(raw_refs: list[dict]) -> list[OnlineReference]:
    references: list[OnlineReference] = []
    for item in raw_refs[:10]:
        references.append(
            OnlineReference(
                title=str(item.get("title") or "").strip(),
                url=str(item.get("url") or "").strip(),
                snippet=str(item.get("snippet") or "").strip(),
            )
        )
    return references


def _emit_progress(
    callback: Callable[[str, int, str, str | None], None] | None,
    stage: str,
    progress: int,
    message: str,
    current_file: str | Path | None = None,
) -> None:
    if callback is None:
        return
    text_path = str(current_file) if current_file else None
    callback(stage, max(0, min(progress, 100)), message, text_path)


def _peek_first_dataset_image(dataset_root: Path) -> Path | None:
    if not dataset_root.exists():
        return None
    for path in dataset_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES:
            return path
    return None


def _execute_analysis(
    query: str,
    top_k: int,
    progress_callback: Callable[[str, int, str, str | None], None] | None = None,
) -> AnalyzeTextResponse:
    system = get_system()
    first_hint_path = _peek_first_dataset_image(system.dataset_root)
    _emit_progress(
        progress_callback,
        "scanning",
        3,
        "Preparing dataset index...",
        first_hint_path,
    )

    with _SYSTEM_LOCK:
        def on_index_progress(stage: str, progress: int, message: str, current_file: Path | None) -> None:
            mapped_stage = "indexing" if stage == "indexing" else "scanning"
            mapped_progress = max(3, min(progress, 62))
            _emit_progress(progress_callback, mapped_stage, mapped_progress, message, current_file)

        system.refresh_local_dataset_index(progress_callback=on_index_progress)
        _emit_progress(progress_callback, "local_search", 66, "Running local semantic search...")

        detected_topic = system.detect_topic(query)
        detected_task = system.detect_task(query)

        matches: list[tuple[Path, float]] = []
        if system.faiss_manager is not None and system.faiss_manager.has_loaded_index():
            query_embedding = system._get_clip_model().encode_text(query)[0]
            raw_results = system.faiss_manager.search(query_embedding, top_k=top_k)
            matches = [(Path(path), float(score)) for path, score in raw_results]

        first_match = matches[0][0] if matches else None
        _emit_progress(
            progress_callback,
            "local_search",
            70,
            f"Local retrieval complete with {len(matches)} matches.",
            first_match,
        )

        caption_targets = [path for path, _ in matches[:3]]
        captions = system._generate_captions(caption_targets) if caption_targets else {}

        _emit_progress(progress_callback, "online_search", 76, "Collecting online references...")
        online_references = system._run_online_text_search(query=query, top_k=max(top_k, 8))

        _emit_progress(progress_callback, "graphs", 86, "Building trend graphs from dataset...")
        graph_paths, graph_summary = system._build_graphs()

        _emit_progress(progress_callback, "summarizing", 93, "Preparing summary and evidence cards...")
        reasoning_title, reasoning = system._generate_context_aware_reasoning(
            query=query,
            topic=detected_topic,
            task=detected_task,
            visual_captions=captions,
            online_references=online_references,
        )

    response_matches: list[DatasetMatch] = []
    for idx, (path, similarity) in enumerate(matches, start=1):
        lat, lng = _stable_geo_from_text(str(path))
        clipped_score = max(min(float(similarity), 1.0), 0.0)
        response_matches.append(
            DatasetMatch(
                id=f"patch-{idx}",
                file_path=str(path),
                similarity=clipped_score,
                confidence=clipped_score,
                lat=lat,
                lng=lng,
                label=path.stem,
                caption=captions.get(str(path)),
            )
        )

    graph_artifacts: list[GraphArtifact] = []
    for path in graph_paths:
        if not path.exists():
            continue
        url = _output_file_url(path)
        if not url:
            continue
        graph_artifacts.append(GraphArtifact(path=str(path), url=url))

    references = _to_references(online_references)
    if response_matches:
        local_message = f"Found {len(response_matches)} local matches for '{query}'."
    else:
        local_message = "No local matches found in the indexed dataset."
    if references:
        status_message = f"{local_message} Retrieved {len(references)} online references."
    else:
        status_message = f"{local_message} Online references unavailable."

    return AnalyzeTextResponse(
        query=query,
        detected_topic=detected_topic,
        detected_task=detected_task,
        dataset_root=str(system.dataset_root),
        total_matches=len(response_matches),
        matches=response_matches,
        status_message=status_message,
        reasoning_title=reasoning_title,
        reasoning=reasoning,
        online_references=references,
        graph_summary=graph_summary,
        graphs=graph_artifacts,
    )


def _set_job(job_id: str, **updates: Any) -> None:
    with _JOB_LOCK:
        job = _ANALYSIS_JOBS.get(job_id)
        if job is None:
            return
        if "current_file" in updates and updates["current_file"] is None:
            updates.pop("current_file")
        job.update(updates)


def _get_job(job_id: str) -> dict[str, Any] | None:
    with _JOB_LOCK:
        return _ANALYSIS_JOBS.get(job_id)


def _run_analysis_job(job_id: str, query: str, top_k: int) -> None:
    dataset_error_type = _project_api()["dataset_error"]

    def update(stage: str, progress: int, message: str, current_file: str | None = None) -> None:
        _set_job(
            job_id,
            status="running",
            stage=stage,
            progress=progress,
            message=message,
            current_file=current_file,
        )

    try:
        result = _execute_analysis(query=query, top_k=top_k, progress_callback=update)
        _set_job(
            job_id,
            status="completed",
            stage="complete",
            progress=100,
            message="Analysis complete.",
            current_file=None,
            result=result.model_dump(),
        )
    except dataset_error_type as exc:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            progress=100,
            message="Dataset error during analysis.",
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            progress=100,
            message="Unexpected failure during analysis.",
            error=str(exc),
        )


def _serialize_job(job_id: str, payload: dict[str, Any]) -> AnalyzeTextJobStatusResponse:
    raw_result = payload.get("result")
    parsed_result = AnalyzeTextResponse(**raw_result) if isinstance(raw_result, dict) else None
    return AnalyzeTextJobStatusResponse(
        job_id=job_id,
        status=str(payload.get("status") or "unknown"),
        stage=str(payload.get("stage") or "unknown"),
        progress=int(payload.get("progress") or 0),
        message=str(payload.get("message") or ""),
        current_file=payload.get("current_file"),
        error=payload.get("error"),
        result=parsed_result,
    )


app = FastAPI(title="FusionX Bridge API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://169.254.114.73:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/output-files", StaticFiles(directory=str(OUTPUT_DIR)), name="output-files")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dataset-status", response_model=DatasetStatusResponse)
def dataset_status() -> DatasetStatusResponse:
    api = _project_api()
    system = get_system()

    discover_images = api["discover_images"]
    preview_paths = api["dataset_preview_paths"]

    image_paths = discover_images(system.dataset_root)
    samples = preview_paths(image_paths, sample_size=5)
    indexed = bool(system.faiss_manager and system.faiss_manager.has_loaded_index())

    return DatasetStatusResponse(
        dataset_root=str(system.dataset_root),
        total_images=len(image_paths),
        sample_paths=samples,
        indexed=indexed,
    )


@app.post("/analyze-text", response_model=AnalyzeTextResponse)
def analyze_text(payload: AnalyzeTextRequest) -> AnalyzeTextResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    dataset_error_type = _project_api()["dataset_error"]
    try:
        return _execute_analysis(query=query, top_k=payload.top_k)
    except dataset_error_type as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to process semantic query: {exc}") from exc


@app.post("/analyze-text/start", response_model=AnalyzeTextJobStartResponse)
def analyze_text_start(payload: AnalyzeTextRequest) -> AnalyzeTextJobStartResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    system = get_system()
    hint_path = _peek_first_dataset_image(system.dataset_root)
    job_id = uuid.uuid4().hex
    with _JOB_LOCK:
        _ANALYSIS_JOBS[job_id] = {
            "status": "running",
            "stage": "scanning",
            "progress": 1,
            "message": "Initializing analysis pipeline...",
            "current_file": str(hint_path) if hint_path else None,
            "error": None,
            "result": None,
        }

    worker = threading.Thread(
        target=_run_analysis_job,
        args=(job_id, query, payload.top_k),
        daemon=True,
    )
    worker.start()

    return AnalyzeTextJobStartResponse(
        job_id=job_id,
        status="running",
        message="Analysis job started.",
    )


@app.get("/analysis-jobs/{job_id}", response_model=AnalyzeTextJobStatusResponse)
def analyze_text_job_status(job_id: str) -> AnalyzeTextJobStatusResponse:
    payload = _get_job(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Unknown analysis job: {job_id}")
    return _serialize_job(job_id, payload)


@app.post("/encode-image", response_model=EncodeImageResponse)
async def encode_image(file: UploadFile = File(...)) -> EncodeImageResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="No image bytes provided.")

    try:
        with Image.open(io.BytesIO(content)) as img:
            image = img.convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid image file: {exc}") from exc

    system = get_system()
    try:
        with _SYSTEM_LOCK:
            embedding = system._get_clip_model().encode_pil_image(image)[0]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Image embedding failed: {exc}") from exc

    vector = np.asarray(embedding, dtype=np.float32)
    digest = hashlib.sha1(vector.tobytes()).hexdigest()[:16].upper()
    code = f"VX-{digest}"
    preview = [round(float(v), 6) for v in vector[:12]]

    return EncodeImageResponse(
        unique_math_code=code,
        embedding_dim=int(vector.shape[0]),
        vector_preview=preview,
    )
