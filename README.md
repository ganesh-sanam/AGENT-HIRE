# AgentHire AI ⚡

**AgentHire AI** is an advanced, production-grade multi-agent resume evaluation, ATS optimization, and professional PDF generation web application.

Built with **FastAPI**, **LangGraph**, **Groq LPUs**, **PyMuPDF**, **ReportLab**, and a modern **React 18** web application, AgentHire AI evaluates resumes against real job postings, enforces a strict anti-hallucination policy, allows candidates to confirm genuine competencies, and outputs beautifully formatted, ATS-compliant resumes ready for submission.

---

## Architecture Overview

```
                                  +------------------------------+
                                  |   User Browser (React UI)    |
                                  +--------------+---------------+
                                                 |
                                         REST API / JSON
                                                 |
                                                 v
                                  +------------------------------+
                                  |     FastAPI Backend (:8000)   |
                                  +--------------+---------------+
                                                 |
                      +--------------------------+--------------------------+
                      |                                                     |
                      v                                                     v
          +-----------------------+                             +-----------------------+
          |   LangGraph Pipeline  |                             |  SQLite Session Store |
          +-----------+-----------+                             |     (sessions.db)     |
                      |                                         +-----------------------+
      +---------------+---------------+
      |               |               |
      v               v               v
+-----------+   +-----------+   +-----------+
| Parser    |   | Evaluator |   | Optimizer |
| Agent     |   | Agent     |   | Agent     |
+-----------+   +-----------+   +-----------+
      |               |               |
      +---------------+---------------+
                      |
                      v
         +--------------------------+
         | Groq API (openai/gpt-oss)|
         +--------------------------+
                      |
                      v
         +--------------------------+
         | Professional PDF Engine  |
         |  (ReportLab Vector PDF)  |
         +--------------------------+
```

---

## Key Features

1. **Deterministic & LLM Hybrid Evaluation**:
   - Scores candidate resumes across 5 key ATS dimensions:
     - **Technical Skills Match** (35 pts max)
     - **Project & Experience Relevance** (25 pts max)
     - **Education & Qualifications** (15 pts max, deterministic scoring)
     - **ATS Formatting & Compatibility** (15 pts max)
     - **Clarity & Presentation** (10 pts max)
   - Total score: 100 points maximum.

2. **Strict Anti-Hallucination & Watchlist Guards**:
   - Candidate experience, education, employers, degrees, metrics, and dates are strictly immutable.
   - Identified skill gaps are presented to the candidate for explicit verification.
   - Confirmed skills may only be added to the technical skills array; the system refuses to fabricate projects or work history.
   - **Empty confirmation (`[]`) is 100% valid and supported**: When zero skills are confirmed, the optimizer tailors phrasing and keyword alignment of the candidate's existing background with zero unverified additions.

3. **Transparent Score Audit & Explanations**:
   - Transparently distinguishes presentation and keyword prominence improvements from verified skill additions.
   - Every optimization returns `initial_score`, `score`, `score_delta`, and a plain-English `score_explanation`.

4. **Production ReportLab PDF Engine**:
   - Generates clean, publication-quality, single-page or two-page A4 PDFs with zero literal HTML tags (`<b>`, `</b>`) or raw JSON/Python list dumps (`['...']`).
   - Grouped technical skills hierarchy (Languages, AI/ML & Frameworks, LLMs/Agents/RAG, Developer Tools & Databases).
   - Clean project bullet formatting with italic technology lines.
   - Safe KeepTogether flowables to eliminate orphaned headings.

5. **Durable Session Persistence**:
   - Thread-safe SQLite database (`outputs/sessions.db`) stores session state, evaluations, and optimization history.
   - Sessions survive server reboots and reloads.
   - Supabase schema included (`supabase_schema.sql`) for cloud Postgres and private S3-compatible PDF storage.

6. **Full-Featured React 18 Web UI**:
   - Responsive 4-step wizard:
     1. **Upload & Match**: Drag-and-drop PDF resume and paste target job description.
     2. **ATS Evaluation**: Visual score badge, category progress bars, verified strengths, and requirements list.
     3. **Skill Confirmation**: Interactive checkboxes with "Select All", "Clear All", and explicit support for empty confirmation.
     4. **Optimized Profile & Download**: Score impact comparison card, audit explanation, profile preview, and one-click PDF download.

---

## Project Structure

```text
AGENT_HIRE/
├── agents/
│   ├── resume_parser.py          # Extracts structured JSON from raw resume text
│   ├── resume_evaluator.py       # Hybrid deterministic/LLM ATS evaluation
│   └── resume_optimizer.py       # Conservative rewriting with anti-hallucination watchlist
│
├── workflow/
│   ├── graph.py                  # LangGraph StateGraph (analysis & optimization workflows)
│   └── state.py                  # AgentHireState TypedDict definition
│
├── services/
│   ├── llm_service.py            # Groq ChatGroq client provider
│   ├── pdf_service.py            # PyMuPDF (fitz) text extraction engine
│   ├── resume_output_service.py  # Production ReportLab PDF generator
│   └── vectore_store.py          # ChromaDB semantic embeddings store
│
├── api/
│   └── main.py                   # FastAPI REST API, SQLite session manager & routes
│
├── frontend/
│   ├── index.html                # Zero-build standalone React 18 single-page application
│   ├── package.json              # Vite / React package specification
│   ├── vite.config.js            # Vite configuration with API proxy
│   └── app.py                    # Python launcher script
│
├── outputs/
│   ├── uploads/                  # Temporary upload directory
│   ├── resumes/                  # Generated PDF resumes
│   ├── json/                     # Optimized resume JSON snapshots
│   └── sessions.db               # SQLite persistent session database
│
├── tests/
│   └── test_pipeline.py          # Test suite covering PDF engine, API, and sessions
│
├── supabase_schema.sql           # Production Supabase PostgreSQL & Storage configuration
├── vercel.json                   # Vercel deployment routing configuration
├── requirements.txt              # Pinned Python package dependencies
├── .env                          # Local environment variables (excluded from git)
├── .gitignore                    # Git ignore file for secrets and generated outputs
└── README.md                     # Documentation
```

---

## Local Development & Setup

### 1. Prerequisites
- Python 3.10+ (Python 3.13 tested and verified)
- Valid Groq API key from [console.groq.com](https://console.groq.com)

### 2. Environment Configuration
Create or verify `.env` in the project root:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
```

### 3. Virtual Environment & Dependencies
```powershell
# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install or verify requirements
python -m pip install --upgrade pip
pip install -r requirements.txt
pip check
```

### 4. Running the Web Application
Start the FastAPI server:
```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

- **Web Application UI**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
- **Interactive Swagger Docs**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
- **Health Check**: Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

---

## Running the Automated Test Suite

Run the test suite:
```powershell
.\.venv\Scripts\python.exe -u -c "
from tests.test_pipeline import *
from pathlib import Path
tmp = Path('outputs/test_tmp')
tmp.mkdir(parents=True, exist_ok=True)
test_pdf_generation_formatting(tmp)
test_skills_categorization()
test_split_into_bullets()
test_sqlite_session_store(tmp)
test_api_health()
test_api_home_html()
test_api_download_security()
print('ALL 7 TESTS PASSED!')
"
```

---

## Production Deployment Guide

### Deployment Architecture
- **Frontend**: Deploy `frontend/` to **Vercel** (Global Edge CDN, instant loading, SSL).
- **Backend**: Deploy FastAPI backend to **Railway**, **Render**, or **Fly.io** (Persistent process, no 10-second serverless timeout, native PyMuPDF & ReportLab support).
- **Database & Storage (Optional for scale)**: **Supabase** (Postgres for session state, Supabase Storage for private PDF resumes).

### Environment Variables for Deployment
Configure these in your hosting dashboard (never commit them to Git):

| Variable | Description | Example / Default |
|---|---|---|
| `GROQ_API_KEY` | Groq API Key (Required) | `gsk_...` |
| `GROQ_MODEL` | Groq Model Name | `openai/gpt-oss-120b` |
| `CORS_ORIGINS` | Allowed Frontend Origins | `https://your-agenthire-frontend.vercel.app` |
| `VITE_API_BASE_URL` | Frontend API URL (if separate) | `https://your-backend.railway.app` |

### Vercel Deployment (Frontend)
1. Push this repository to GitHub (ensure `.env` is ignored).
2. Connect your repository to Vercel.
3. Set the Root Directory to `frontend`.
4. Add environment variable `VITE_API_BASE_URL` pointing to your deployed FastAPI backend URL.
5. Deploy.

---

## API Reference

### 1. `GET /health`
Returns system status and API health.
```json
{
  "status": "healthy",
  "service": "AgentHire AI API",
  "version": "1.4.0",
  "groq_configured": true
}
```

### 2. `POST /analyze-resume`
Uploads a resume PDF and target job description for ATS analysis.
- **Request**: Multipart Form Data (`resume: File`, `job_description: string`).
- **Response**:
```json
{
  "session_id": "56dac4070ec24e4881d018fbd5c1b359",
  "status": "pending_confirmation",
  "score": 77,
  "initial_score": 77,
  "threshold": 80,
  "approved": false,
  "original_evaluation": {
    "category_scores": { ... },
    "strengths": [ ... ],
    "weaknesses": [ ... ]
  },
  "unconfirmed_skills": ["tool calling", "Azure OpenAI", "Kubernetes"],
  "pending_confirmation": true,
  "message": "Review the skill gaps and confirm only skills you genuinely possess."
}
```

### 3. `POST /confirm-skills`
Confirms genuine skills (empty list `[]` allowed) and triggers optimization and PDF generation.
- **Request Body**:
```json
{
  "session_id": "56dac4070ec24e4881d018fbd5c1b359",
  "confirmed_skills": []
}
```
- **Response**:
```json
{
  "session_id": "56dac4070ec24e4881d018fbd5c1b359",
  "status": "completed",
  "score": 83,
  "initial_score": 77,
  "score_delta": 6,
  "score_explanation": "Score increased by 6 points (77 -> 83). No unconfirmed skills were added. Improvement is driven by clearer ATS phrasing, prominent keyword organization, and refined presentation of your existing verified experience.",
  "approved": true,
  "pdf_download_url": "/download-resume/optimized_resume_56dac4070ec24e4881d018fbd5c1b359.pdf"
}
```

### 4. `GET /download-resume/{filename}`
Securely downloads the generated PDF resume with strict path traversal validation.

---

## License
MIT License &copy; 2026 AgentHire AI.
