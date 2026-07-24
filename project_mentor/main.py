"""Loopback-only web application for Project Mentor Phase 6."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from project_mentor import PHASE, __version__
from project_mentor.ai_service import (
    AIErrorCode,
    GroundedAIService,
    select_default_model,
)
from project_mentor.config import Settings
from project_mentor.context_builder import EvidenceContextBuilder
from project_mentor.debug_service import (
    DebugInvestigationError,
    DebugInvestigationService,
)
from project_mentor.ollama_client import OllamaClient
from project_mentor.scanner import scan_project
from project_mentor.scan_store import ScanStore
from project_mentor.teach_service import TeachLessonError, TeachLessonService


PACKAGE_DIRECTORY = Path(__file__).resolve().parent
STATIC_DIRECTORY = PACKAGE_DIRECTORY / "static"
SETTINGS = Settings.from_env()
OLLAMA_CLIENT = OllamaClient(SETTINGS)
AI_SERVICE = GroundedAIService(
    SETTINGS,
    OLLAMA_CLIENT,
    EvidenceContextBuilder(SETTINGS.max_evidence_chars),
)
SCAN_STORE = ScanStore()
TEACH_SERVICE = TeachLessonService()
DEBUG_SERVICE = DebugInvestigationService()

app = FastAPI(
    title="Project Mentor",
    description="Understand a Python repository using deterministic source analysis.",
    version=__version__,
)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")


class ScanRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2_000)


class ExplainRequest(BaseModel):
    scan_id: str = Field(min_length=16, max_length=128)
    model: str = Field(min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=2_000)
    symbol_id: str | None = Field(default=None, max_length=1_000)


class TeachLessonRequest(BaseModel):
    scan_id: str = Field(min_length=16, max_length=128)
    symbol_id: str = Field(min_length=1, max_length=1_000)


class TeachExplainRequest(TeachLessonRequest):
    model: str = Field(min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=2_000)


class DebugInvestigationRequest(BaseModel):
    scan_id: str = Field(min_length=16, max_length=128)
    symbol_id: str = Field(min_length=1, max_length=1_000)
    failure_statement: str = Field(min_length=1, max_length=2_000)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIRECTORY / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "phase": PHASE, "version": __version__}


def _choose_folder() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="Select a Python project folder")
        root.destroy()
        return selected
    except Exception as exc:  # The manual path field remains available.
        raise RuntimeError(
            "The Windows folder picker could not open. Enter the folder path manually."
        ) from exc


@app.get("/api/pick-folder")
async def pick_folder() -> dict[str, str]:
    try:
        selected = await run_in_threadpool(_choose_folder)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": selected}


@app.post("/api/scan")
async def scan(payload: ScanRequest, response: Response) -> dict:
    try:
        result = await run_in_threadpool(scan_project, payload.path.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response.headers["X-Project-Mentor-Scan-ID"] = SCAN_STORE.put(result)
    return result.to_dict()


@app.get("/api/ollama/status")
async def ollama_status() -> dict:
    result = await OLLAMA_CLIENT.list_models()
    endpoint_risk = None
    if not SETTINGS.ollama_is_loopback:
        endpoint_risk = (
            "This endpoint is not loopback. Repository evidence sent to it can leave "
            "this computer. Use only a server you trust."
        )
    if not result.ok:
        return {
            "connected": False,
            "endpoint": SETTINGS.ollama_base_url,
            "endpoint_is_loopback": SETTINGS.ollama_is_loopback,
            "endpoint_risk": endpoint_risk,
            "models": [],
            "selected_model": None,
            "configured_default_model": SETTINGS.ollama_default_model or None,
            "error": {
                "code": result.error.code.value,
                "message": result.error.message,
            },
        }
    models = result.value or []
    selected = select_default_model(models, SETTINGS.ollama_default_model)
    names = {item.name for item in models}
    default_warning = None
    if SETTINGS.ollama_default_model and SETTINGS.ollama_default_model not in names:
        default_warning = (
            "The configured default model is not installed; choose an installed model."
        )
    return {
        "connected": True,
        "endpoint": SETTINGS.ollama_base_url,
        "endpoint_is_loopback": SETTINGS.ollama_is_loopback,
        "endpoint_risk": endpoint_risk,
        "models": [
            {
                "name": item.name,
                "size": item.size,
                "parameter_size": item.parameter_size,
                "quantization_level": item.quantization_level,
            }
            for item in models
        ],
        "selected_model": selected,
        "configured_default_model": SETTINGS.ollama_default_model or None,
        "default_warning": default_warning,
        "error": None,
    }


@app.post("/api/ai/explain")
async def explain_with_ollama(payload: ExplainRequest) -> dict:
    analysis = SCAN_STORE.get(payload.scan_id)
    if analysis is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "scan_expired",
                "message": "This scan is no longer available. Scan the project again.",
            },
        )
    result = await AI_SERVICE.explain(
        analysis,
        model=payload.model.strip(),
        question=payload.question,
        selected_symbol_id=payload.symbol_id,
        workflow="map",
    )
    if not result.ok:
        status_code = (
            503
            if result.error.code in {AIErrorCode.OLLAMA, AIErrorCode.NO_MODELS}
            else 400
        )
        detail = {
            "code": result.error.code.value,
            "message": result.error.message,
        }
        if result.error.ollama_error is not None:
            detail["failure_type"] = result.error.ollama_error.code.value
        raise HTTPException(status_code=status_code, detail=detail)
    return result.response.to_dict()


def _trusted_scan(scan_id: str):
    analysis = SCAN_STORE.get(scan_id)
    if analysis is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "scan_expired",
                "message": "This scan is no longer available. Scan the project again.",
            },
        )
    return analysis


async def _teach_bundle(scan_id: str, symbol_id: str):
    analysis = _trusted_scan(scan_id)
    try:
        bundle = await run_in_threadpool(
            TEACH_SERVICE.build, analysis, symbol_id.strip()
        )
    except TeachLessonError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return analysis, bundle


@app.post("/api/teach/lesson")
async def build_teach_lesson(payload: TeachLessonRequest) -> dict:
    """Return deterministic lesson data without contacting Ollama."""

    _, bundle = await _teach_bundle(payload.scan_id, payload.symbol_id)
    return bundle.lesson.to_dict()


@app.post("/api/teach/explain")
async def explain_teach_lesson(payload: TeachExplainRequest) -> dict:
    """Interpret only the allow-listed evidence used by a trusted lesson."""

    analysis, bundle = await _teach_bundle(payload.scan_id, payload.symbol_id)
    result = await AI_SERVICE.explain(
        analysis,
        model=payload.model.strip(),
        question=payload.question,
        selected_symbol_id=payload.symbol_id,
        workflow="teach",
        evidence_items=bundle.evidence_items,
    )
    if not result.ok:
        status_code = (
            503
            if result.error.code in {AIErrorCode.OLLAMA, AIErrorCode.NO_MODELS}
            else 400
        )
        detail = {
            "code": result.error.code.value,
            "message": result.error.message,
        }
        if result.error.ollama_error is not None:
            detail["failure_type"] = result.error.ollama_error.code.value
        raise HTTPException(status_code=status_code, detail=detail)
    return {
        "lesson_id": bundle.lesson.lesson_id,
        "grounded_response": result.response.to_dict(),
    }


@app.post("/api/debug/investigation")
async def build_debug_investigation(payload: DebugInvestigationRequest) -> dict:
    """Return a deterministic investigation without contacting Ollama."""

    analysis = _trusted_scan(payload.scan_id)
    try:
        bundle = await run_in_threadpool(
            DEBUG_SERVICE.build,
            analysis,
            payload.symbol_id.strip(),
            payload.failure_statement,
        )
    except DebugInvestigationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return bundle.investigation.to_dict()
