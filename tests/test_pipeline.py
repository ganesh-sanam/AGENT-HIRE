import json
import re
from pathlib import Path
import fitz
from fastapi.testclient import TestClient

from api.main import app, sessions_store, BASE_DIR, OUTPUT_DIR
from services.resume_output_service import generate_resume_pdf, categorize_skills, split_into_bullets
from workflow.graph import optimization_graph


SAMPLE_RESUME_DATA = {
    "name": "Alex Mercer",
    "email": "alex.mercer@example.com",
    "phone": "+1 (555) 234-5678",
    "summary": (
        "Senior Generative AI Engineer with 4+ years of experience designing multi-agent workflows, "
        "production Retrieval-Augmented Generation (RAG) architectures, and fine-tuning open-weights models. "
        "Proven expertise in LangGraph, FastAPI, ChromaDB, and hybrid retrieval systems."
    ),
    "skills": [
        "Python", "SQL", "C++", "PyTorch", "LangGraph", "FastAPI",
        "ChromaDB", "SQLite", "Docker", "Git", "RAG", "LLM APIs",
        "Multi-Agent Systems", "Text Embeddings", "Vector Databases",
        "BM25", "Hybrid Search", "Reciprocal Rank Fusion", "Cross-Encoder Reranking"
    ],
    "education": [
        {
            "institution": "University of Technology",
            "degree": "B.S. in Computer Science & Artificial Intelligence",
            "years": "2019 - 2023",
            "details": "GPA: 3.9/4.0, Magna Cum Laude"
        }
    ],
    "projects": [
        {
            "name": "AutoHire Multi-Agent ATS",
            "technologies": ["Python", "LangGraph", "FastAPI", "ChromaDB", "ReportLab"],
            "description": (
                "Architected a distributed multi-agent system coordinating 5 specialized agents. "
                "Integrated ChromaDB for semantic search across 50,000+ candidate profiles with sub-second latency. "
                "Deployed resilient FastAPI backend with automated ReportLab PDF generation pipeline."
            )
        },
        {
            "name": "LegalRAG Statutory Intelligence",
            "technologies": ["PyTorch", "HuggingFace", "BM25", "Sentence Transformers"],
            "description": (
                "Built an enterprise hybrid retrieval engine combining BM25 and dense vector representations via RRF. "
                "Achieved 91.4% nDCG@10 on legal retrieval benchmarks, reducing citation hallucination by 42%."
            )
        }
    ],
    "experience": [
        {
            "role": "AI Engineer",
            "company": "Apex AI Labs",
            "location": "San Francisco, CA",
            "dates": "2023 - Present",
            "description": (
                "Lead development of autonomous agent workflows and RAG pipelines for Fortune 500 clients. "
                "Engineered custom evaluation harnesses to quantify hallucination and retrieval precision."
            )
        }
    ],
    "certifications": [
        "DeepLearning.AI Deep Learning Specialization",
        "AWS Certified Machine Learning - Specialty"
    ],
    "original_text": "Alex Mercer | alex.mercer@example.com | San Francisco, CA"
}


def test_pdf_generation_formatting(tmp_path):
    """Verify that PDF generation produces clean layout with NO literal tags or list syntax."""
    pdf_out = tmp_path / "test_resume.pdf"
    res_path = generate_resume_pdf(SAMPLE_RESUME_DATA, str(pdf_out))
    assert Path(res_path).is_file()

    doc = fitz.open(res_path)
    assert len(doc) >= 1

    full_text = "".join(page.get_text() for page in doc)

    # 1. Check for literal HTML/ReportLab tags that should have been rendered as formatting
    forbidden_tags = ["<b>", "</b>", "<font", "</font>", "<i>", "</i>", "&bull;", "&mdash;", "&nbsp;"]
    for tag in forbidden_tags:
        assert tag not in full_text, f"Literal tag found in PDF text: {tag}"

    # 2. Check for raw Python list syntax
    assert "['" not in full_text, "Raw Python list syntax detected in PDF"
    assert "']" not in full_text, "Raw Python list syntax detected in PDF"

    # 3. Check for core content presence
    assert "Alex Mercer" in full_text
    assert "AutoHire Multi-Agent ATS" in full_text
    assert "Apex AI Labs" in full_text
    assert "University of Technology" in full_text
    assert "TECHNICAL SKILLS" in full_text


def test_skills_categorization():
    """Verify that skills are categorized cleanly without losing skills."""
    skills = ["Python", "PyTorch", "FastAPI", "LangGraph", "ChromaDB"]
    cats = categorize_skills(skills)
    assert "Languages" in cats
    assert "Python" in cats["Languages"]
    assert "AI/ML & Frameworks" in cats
    assert "PyTorch" in cats["AI/ML & Frameworks"]


def test_split_into_bullets():
    """Verify that sentences are cleanly converted into bullet items."""
    text = "First achievement was remarkable. Second achievement improved metrics by 20%. Third was deployment."
    bullets = split_into_bullets(text)
    assert len(bullets) == 3
    assert bullets[0] == "First achievement was remarkable."


def test_sqlite_session_store(tmp_path):
    """Verify SQLite session storage saves and loads state reliably."""
    db_file = tmp_path / "test_sessions.db"
    from api.main import SQLiteSessionStore
    store = SQLiteSessionStore(db_file)

    session_id = "test_sess_123"
    test_state = {"score": 85, "status": "pending_confirmation", "unconfirmed_skills": ["Docker"]}

    store.save(session_id, "pending_confirmation", test_state)
    loaded = store.get(session_id)
    assert loaded is not None
    assert loaded["status"] == "pending_confirmation"
    assert loaded["state"]["score"] == 85
    assert loaded["state"]["unconfirmed_skills"] == ["Docker"]


def test_api_health():
    """Verify API health endpoint."""
    from api.main import health_check
    data = health_check()
    assert data["status"] == "healthy"
    assert "groq_configured" in data


def test_api_home_html():
    """Verify API root serves HTML frontend when requested by browser."""
    from starlette.requests import Request
    from api.main import home
    req = Request({"type": "http", "headers": [(b"accept", b"text/html")]})
    res = home(req)
    assert res.status_code == 200
    content = res.body.decode("utf-8")
    assert "AgentHire AI" in content
    assert "<!DOCTYPE html>" in content


def test_api_download_security():
    """Verify download endpoint rejects traversal attempts and non-existent files."""
    from fastapi import HTTPException
    from api.main import download_resume

    # 1. Path traversal rejected with 400
    try:
        download_resume("../../etc/passwd")
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 400

    # 2. Non-existent file rejected with 404
    try:
        download_resume("optimized_resume_nonexistent12345.pdf")
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 404

    # 3. Valid file downloads correctly
    test_pdf = OUTPUT_DIR / "optimized_resume_test_client.pdf"
    generate_resume_pdf(SAMPLE_RESUME_DATA, str(test_pdf))
    try:
        res = download_resume(test_pdf.name)
        assert res.status_code == 200
        assert Path(res.path).is_file()
    finally:
        test_pdf.unlink(missing_ok=True)


if __name__ == "__main__":
    import tempfile
    print("--- Running test_pdf_generation_formatting ---")
    test_pdf_generation_formatting(Path(tempfile.gettempdir()))
    print("PASSED")

    print("--- Running test_skills_categorization ---")
    test_skills_categorization()
    print("PASSED")

    print("--- Running test_split_into_bullets ---")
    test_split_into_bullets()
    print("PASSED")

    print("--- Running test_sqlite_session_store ---")
    test_sqlite_session_store(Path(tempfile.gettempdir()))
    print("PASSED")

    print("--- Running test_api_health ---")
    test_api_health()
    print("PASSED")

    print("--- Running test_api_home_html ---")
    test_api_home_html()
    print("PASSED")

    print("--- Running test_api_download_security ---")
    test_api_download_security()
    print("PASSED")

    print("\n==========================================")
    print("ALL 7 PIPELINE & API TESTS PASSED SUCCESSFULLY!")
    print("==========================================")

