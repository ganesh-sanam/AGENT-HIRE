import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def get_writable_dir(subfolder: str = "") -> Path:
    """
    Returns a guaranteed writable directory path.
    On Vercel Serverless / AWS Lambda, the app root is read-only, so /tmp is used.
    In local development, BASE_DIR / "outputs" / subfolder is used.
    """
    is_serverless = bool(
        os.getenv("VERCEL")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("VERCEL_ENV")
    )

    if is_serverless:
        target = Path(tempfile.gettempdir()) / "agenthire" / subfolder
    else:
        try:
            target = BASE_DIR / "outputs" / subfolder
            target.mkdir(parents=True, exist_ok=True)
            return target
        except (OSError, PermissionError):
            target = Path(tempfile.gettempdir()) / "agenthire" / subfolder

    target.mkdir(parents=True, exist_ok=True)
    return target


UPLOAD_DIR = get_writable_dir("uploads")
OUTPUT_DIR = get_writable_dir("resumes")
JSON_DIR = get_writable_dir("json")
SESSIONS_DB_PATH = get_writable_dir("data") / "sessions.db"
