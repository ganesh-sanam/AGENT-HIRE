import json
import os
import re
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from workflow.graph import analysis_graph, optimization_graph

from services.storage_service import BASE_DIR, UPLOAD_DIR, OUTPUT_DIR, SESSIONS_DB_PATH

TEMPLATES_DIR = BASE_DIR / "templates"
FRONTEND_DIR = BASE_DIR / "frontend"
DB_PATH = SESSIONS_DB_PATH

DEFAULT_THRESHOLD = 80
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB limit


def get_frontend_html() -> str | None:
    for path in [TEMPLATES_DIR / "index.html", FRONTEND_DIR / "index.html"]:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


# =====================================================================
# PERSISTENT SESSION STORE (SQLite-backed)
# =====================================================================

class SQLiteSessionStore:
    """Thread-safe persistent session store that survives server reloads."""

    def __init__(self, db_file: Path):
        self.db_file = db_file
        self.lock = Lock()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_file), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        state_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()

    def get(self, session_id: str) -> dict | None:
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT status, state_json FROM sessions WHERE session_id = ?",
                    (session_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                try:
                    return {
                        "status": row["status"],
                        "state": json.loads(row["state_json"]),
                    }
                except Exception:
                    return None

    def save(self, session_id: str, status: str, state: dict):
        now = datetime.now(timezone.utc).isoformat()
        state_serialized = json.dumps(state, default=str)
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, status, state_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        status = excluded.status,
                        state_json = excluded.state_json,
                        updated_at = excluded.updated_at
                    """,
                    (session_id, status, state_serialized, now, now),
                )
                conn.commit()


sessions_store = SQLiteSessionStore(DB_PATH)


# =====================================================================
# APPLICATION CONFIGURATION
# =====================================================================

app = FastAPI(
    title="AgentHire AI",
    description="Multi-agent resume evaluation and optimization API",
    version="1.4.0",
    redirect_slashes=False,
)

# Enable CORS for local dev, Vite frontends, and Vercel deployments
allowed_origins_env = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

INTERNAL_SKILL_FIELDS = {
    "skill_gaps",
    "missing_skills",
    "keyword_gaps",
    "unconfirmed_skills",
    "excluded_skill_candidates",
}


class ConfirmSkillsRequest(BaseModel):
    session_id: str = Field(min_length=1)
    confirmed_skills: list[str] = Field(default_factory=list)


def normalize_skill(skill: str) -> str:
    """Normalize Unicode hyphens, whitespace, and case for deduplication."""
    replacements = {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
        "\u2014": "-", "\u2015": "-", "\u2212": "-",
    }
    for old, new in replacements.items():
        skill = skill.replace(old, new)
    return " ".join(skill.casefold().split()).strip()


def deduplicate_skills(skills: list[str]) -> list[str]:
    """Preserve display text while removing duplicate skills."""
    result = []
    seen = set()

    for skill in skills or []:
        if not isinstance(skill, str):
            continue
        skill = skill.strip()
        if not skill:
            continue
        key = normalize_skill(skill)
        if key not in seen:
            seen.add(key)
            result.append(skill.replace("\u2011", "-").replace("\u2010", "-"))

    return result


def public_evaluation(evaluation: dict | None) -> dict:
    """Return evaluation details without exposing competing skill-gap lists."""
    if not isinstance(evaluation, dict):
        return {}

    cleaned = dict(evaluation)
    for field in INTERNAL_SKILL_FIELDS:
        cleaned.pop(field, None)

    return cleaned


def public_message(message: str) -> str:
    return message if isinstance(message, str) else ""


# =====================================================================
# ROUTES
# =====================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"},
    )


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AgentHire AI API",
        "version": "1.4.0",
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
    }


@app.get("/")
def home(request: Request):
    html = get_frontend_html()
    if html:
        return HTMLResponse(
            content=html,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    return {
        "message": "AgentHire AI API is running",
        "docs": "/docs",
        "health": "/health",
        "web_app": "/",
    }


@app.post("/analyze-resume")
async def analyze_resume(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
):
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured on the server. Please add GROQ_API_KEY in Vercel Project Settings > Environment Variables.",
        )

    if not resume.filename or Path(resume.filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF resume.",
        )

    if not job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description cannot be empty.",
        )

    session_id = uuid4().hex
    resume_path = UPLOAD_DIR / f"{session_id}.pdf"

    try:
        content = await resume.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded PDF is empty.",
            )

        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail="The uploaded PDF exceeds the 10 MB size limit.",
            )

        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file does not appear to be a valid PDF.",
            )

        resume_path.write_bytes(content)

        result = analysis_graph.invoke(
            {
                "pdf_path": str(resume_path),
                "job_description": job_description.strip(),
                "session_id": session_id,
                "threshold": DEFAULT_THRESHOLD,
            }
        )

        status = result.get("status", "unknown")
        evaluation = result.get("evaluation", {})

        # The canonical deduplicated skill list exposed to the client
        confirmation_list = deduplicate_skills(
            result.get(
                "unconfirmed_skills",
                result.get("skill_gaps", []),
            )
        )

        result["unconfirmed_skills"] = confirmation_list
        score = result.get("score", 0)

        response = {
            "session_id": session_id,
            "status": status,
            "score": score,
            "initial_score": score,
            "threshold": result.get("threshold", DEFAULT_THRESHOLD),
            "approved": False,
            "original_evaluation": public_evaluation(evaluation),
            "unconfirmed_skills": confirmation_list,
            "pending_confirmation": result.get("pending_confirmation", False),
            "message": public_message(result.get("message", "")),
        }

        if status == "insufficient_jd":
            return response

        # Persist session to SQLite store
        sessions_store.save(session_id, status, result)

        if not confirmation_list:
            response["message"] = (
                "Analysis complete. No additional skills require confirmation. "
                "Call /confirm-skills with an empty confirmed_skills list "
                "to generate the optimized resume."
            )

        return response

    except HTTPException:
        raise

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {str(exc)}",
        ) from exc

    finally:
        resume_path.unlink(missing_ok=True)


@app.post("/confirm-skills")
def confirm_skills(request: ConfirmSkillsRequest):
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured on the server. Please add GROQ_API_KEY in Vercel Project Settings > Environment Variables.",
        )

    session_id = request.session_id
    session = sessions_store.get(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found or expired. Analyze the resume again.",
        )

    if session["status"] not in {
        "pending_confirmation",
        "ready_to_optimize",
    }:
        raise HTTPException(
            status_code=409,
            detail="This session has already been processed or cannot continue.",
        )

    state = dict(session["state"])
    allowed_skills = deduplicate_skills(
        state.get("unconfirmed_skills", state.get("skill_gaps", []))
    )

    requested_skills = []
    for skill in request.confirmed_skills:
        if not isinstance(skill, str) or not skill.strip():
            raise HTTPException(
                status_code=400,
                detail="Each confirmed skill must be a non-empty string.",
            )
        requested_skills.append(skill.strip())

    allowed_lookup = {
        normalize_skill(skill): skill
        for skill in allowed_skills
    }

    invalid_skills = [
        skill
        for skill in requested_skills
        if normalize_skill(skill) not in allowed_lookup
    ]

    if invalid_skills:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "Some confirmed skills were not listed for this session."
                ),
                "invalid_skills": invalid_skills,
            },
        )

    confirmed_skills = list(
        dict.fromkeys(
            allowed_lookup[normalize_skill(skill)]
            for skill in requested_skills
        )
    )

    # Confirmation permits a skill-list entry, not fabricated experience
    state["confirmed_skills"] = confirmed_skills
    state["pending_confirmation"] = False

    try:
        result = optimization_graph.invoke(state)

        pdf_path_value = result.get("final_resume_path")
        pdf_path = Path(pdf_path_value) if pdf_path_value else None

        workflow_completed = (
            result.get("status") == "completed"
            and pdf_path is not None
            and pdf_path.is_file()
        )

        score = result.get("score", 0)
        initial_score = result.get("initial_score", state.get("score", score))
        score_delta = result.get("score_delta", score - initial_score)
        score_explanation = result.get(
            "score_explanation",
            f"Resume optimization completed. Score: {score}/100.",
        )

        response = {
            "session_id": session_id,
            "status": result.get("status", "unknown"),
            "score": score,
            "initial_score": initial_score,
            "score_delta": score_delta,
            "score_explanation": score_explanation,
            "threshold": result.get("threshold", DEFAULT_THRESHOLD),
            "approved": workflow_completed,
            "score_is_informational": True,
            "confirmed_skills": confirmed_skills,
            "original_evaluation": public_evaluation(
                result.get("evaluation", {})
            ),
            "updated_evaluation": public_evaluation(
                result.get("updated_evaluation", {})
            ),
            "optimized_resume": result.get("final_resume_data", {}),
            "message": public_message(
                result.get("message", score_explanation)
            ),
        }

        if workflow_completed:
            response["pdf_download_url"] = (
                f"/download-resume/{pdf_path.name}"
            )
        else:
            response["message"] = (
                "The workflow returned, but the PDF file was not found. "
                "Check the server logs."
            )

        # Update persistent session
        new_status = "processed" if workflow_completed else "pending_confirmation"
        sessions_store.save(session_id, new_status, result if workflow_completed else state)

        return response

    except HTTPException:
        raise

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {str(exc)}",
        ) from exc


@app.get("/download-resume/{filename}")
def download_resume(filename: str):
    # Strict filename security against path traversal
    if not re.match(r"^optimized_resume_[a-zA-Z0-9_-]+\.pdf$", filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename format.",
        )

    pdf_path = OUTPUT_DIR / filename

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Resume PDF not found.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
    )
