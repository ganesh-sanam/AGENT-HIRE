import json
import re
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    KeepTogether,
)
from xml.sax.saxutils import escape


def normalize_pdf_text(value):
    """Normalize unsupported Unicode dashes and quotes before PDF generation."""
    if isinstance(value, str):
        for dash in (
            "\u2010", "\u2011", "\u2012", "\u2013",
            "\u2014", "\u2015", "\u2212",
        ):
            value = value.replace(dash, "-")
        quotes = {
            "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"',
            "\u2022": "*", "\u25cf": "*",
        }
        for q, repl in quotes.items():
            value = value.replace(q, repl)
        return value

    if isinstance(value, list):
        return [normalize_pdf_text(item) for item in value]

    if isinstance(value, tuple):
        return tuple(normalize_pdf_text(item) for item in value)

    if isinstance(value, dict):
        return {
            normalize_pdf_text(k) if isinstance(k, str) else k:
            normalize_pdf_text(v)
            for k, v in value.items()
        }

    return value


def categorize_skills(skills) -> dict[str, list[str]]:
    """Group technical skills into readable, ATS-friendly categories."""
    if isinstance(skills, dict):
        return {str(k): [str(s).strip() for s in v if s] for k, v in skills.items()}
    if not isinstance(skills, list):
        return {"Skills": [str(skills).strip()]}

    # Check if items already have category prefixes like "Languages: Python, SQL"
    if any(":" in str(s) for s in skills if isinstance(s, str)):
        categorized = {}
        for s in skills:
            if not isinstance(s, str) or not s.strip():
                continue
            if ":" in s:
                cat, val = s.split(":", 1)
                items = [x.strip() for x in val.split(",") if x.strip()]
                categorized.setdefault(cat.strip(), []).extend(items)
            else:
                categorized.setdefault("Other Technical Skills", []).append(s.strip())
        return categorized

    CAT_MAP = {
        "Languages": {
            "python", "sql", "c++", "c", "java", "javascript", "typescript",
            "bash", "shell", "html", "css", "r", "go", "rust"
        },
        "AI/ML & Frameworks": {
            "pytorch", "tensorflow", "keras", "scikit-learn", "scikit learn",
            "sentence transformers", "opencv", "pandas", "numpy", "scipy",
            "huggingface", "transformers", "xgboost", "lightgbm"
        },
        "LLMs, Agents & RAG": {
            "langgraph", "langchain", "rag", "retrieval augmented generation",
            "llm apis", "llms", "multi-agent systems", "multi-agent orchestration",
            "text embeddings", "vector databases", "bm25", "dense retrieval",
            "hybrid search", "rrf", "cross-encoder reranking", "retrieval evaluation",
            "groq", "ollama", "prompt engineering", "openai", "azure openai",
            "gemini", "anthropic"
        },
        "Developer Tools & Databases": {
            "chromadb", "sqlite", "postgresql", "postgres", "mysql", "mongodb",
            "redis", "pgvector", "faiss", "fastapi", "flask", "streamlit",
            "git", "docker", "kubernetes", "linux", "aws", "gcp", "azure",
            "jupyter", "vs code", "rest apis", "restful apis", "ci/cd"
        }
    }

    result = {k: [] for k in CAT_MAP}
    others = []

    for item in skills:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        matched = False
        for cat_name, terms in CAT_MAP.items():
            if lower in terms or any(t == lower for t in terms):
                result[cat_name].append(cleaned)
                matched = True
                break
        if not matched:
            others.append(cleaned)

    final_cats = {k: v for k, v in result.items() if v}
    if others:
        final_cats["Other Technical Skills"] = others

    return final_cats


def split_into_bullets(text: str) -> list[str]:
    """Split descriptive text into concise, formatted bullet points."""
    if not text:
        return []
    text = str(text).strip()
    if any(b in text for b in ["●", "•", "\n"]):
        parts = re.split(r"[●•\n]+", text)
        return [p.strip() for p in parts if p.strip()]

    # Split by period followed by space and capital letter for multi-sentence descriptions
    sentences = re.split(r"(?<=\.)\s+(?=[A-Z])", text)
    bullets = [s.strip() for s in sentences if s.strip()]
    return bullets if bullets else [text]


def generate_resume_pdf(resume_data: dict, output_path: str) -> str:
    """
    Generate an ATS-friendly, professionally formatted resume PDF from resume JSON.
    Fixes literal markup tags, Python list syntax dumps, orphaned headings, and poor spacing.
    """
    if not isinstance(resume_data, dict) or not resume_data:
        raise ValueError("Valid resume data is required.")

    resume_data = normalize_pdf_text(resume_data)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 0.5 inch margins for professional layout density
    document = SimpleDocTemplate(
        str(output_file),
        pagesize=A4,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styling
    primary_color = colors.HexColor("#17365D")   # Deep Classic Navy
    text_color = colors.HexColor("#222222")      # Off-black readable body
    muted_color = colors.HexColor("#4B5563")     # Slate for dates/details
    divider_color = colors.HexColor("#CBD5E1")   # Crisp divider line

    styles.add(ParagraphStyle(
        name="CandidateName",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        alignment=TA_CENTER,
        textColor=primary_color,
        spaceAfter=3,
    ))

    styles.add(ParagraphStyle(
        name="ContactLine",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        alignment=TA_CENTER,
        textColor=muted_color,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=primary_color,
        spaceBefore=7,
        spaceAfter=2,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="ResumeBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=text_color,
        alignment=TA_JUSTIFY,
        spaceAfter=3,
    ))

    styles.add(ParagraphStyle(
        name="ItemTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=primary_color,
        spaceBefore=2,
        spaceAfter=1,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="ItemSub",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=11,
        textColor=muted_color,
        spaceAfter=2,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="BulletPoint",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=text_color,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2,
    ))

    styles.add(ParagraphStyle(
        name="SkillCategory",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=text_color,
        spaceAfter=2,
    ))

    story = []

    def safe_text(val):
        return escape(str(val)) if val is not None else ""

    def add_section_header(title: str):
        story.append(Paragraph(safe_text(title), styles["SectionHeading"]))
        story.append(HRFlowable(
            width="100%",
            thickness=0.6,
            color=divider_color,
            spaceBefore=1,
            spaceAfter=4,
        ))

    # --- Header ---
    name = resume_data.get("name") or "Candidate Resume"
    story.append(Paragraph(safe_text(name), styles["CandidateName"]))

    contact_parts = []
    if resume_data.get("email"):
        contact_parts.append(safe_text(resume_data["email"]))
    if resume_data.get("phone"):
        contact_parts.append(safe_text(resume_data["phone"]))

    # Look for location and links if present in original_text or metadata
    orig = resume_data.get("original_text", "")
    if "LinkedIn" in orig:
        contact_parts.append("LinkedIn")
    if "GitHub" in orig:
        contact_parts.append("GitHub")
    if "Andhra Pradesh" in orig and not any("Andhra" in p for p in contact_parts):
        contact_parts.append("Andhra Pradesh, India")

    if contact_parts:
        story.append(Paragraph(" &nbsp;|&nbsp; ".join(contact_parts), styles["ContactLine"]))

    # --- Professional Summary ---
    summary = resume_data.get("summary")
    if summary and isinstance(summary, str) and summary.strip():
        add_section_header("PROFESSIONAL SUMMARY")
        story.append(Paragraph(safe_text(summary.strip()), styles["ResumeBody"]))

    # --- Skills ---
    skills = resume_data.get("skills")
    if skills:
        add_section_header("TECHNICAL SKILLS")
        categorized = categorize_skills(skills)
        for cat_name, skill_items in categorized.items():
            if not skill_items:
                continue
            skills_joined = ", ".join(safe_text(s) for s in skill_items)
            cat_safe = safe_text(cat_name)
            line_html = f"<b>{cat_safe}:</b> {skills_joined}"
            story.append(Paragraph(line_html, styles["SkillCategory"]))

    # --- Education ---
    education = resume_data.get("education")
    if education:
        add_section_header("EDUCATION")
        if isinstance(education, list):
            for item in education:
                if isinstance(item, dict):
                    inst = safe_text(item.get("institution", ""))
                    degree = safe_text(item.get("degree", ""))
                    years = safe_text(item.get("years", ""))
                    details = safe_text(item.get("details", ""))

                    line1_parts = []
                    if inst:
                        line1_parts.append(f"<b>{inst}</b>")
                    if degree:
                        line1_parts.append(f"{degree}")
                    line1 = " &mdash; ".join(line1_parts)

                    line2_parts = []
                    if years:
                        line2_parts.append(years)
                    if details:
                        line2_parts.append(details)
                    line2 = " &nbsp;|&nbsp; ".join(line2_parts)

                    edu_block = []
                    if line1:
                        edu_block.append(Paragraph(line1, styles["ItemTitle"]))
                    if line2:
                        edu_block.append(Paragraph(line2, styles["ItemSub"]))
                    story.append(KeepTogether(edu_block))
                else:
                    story.append(Paragraph(f"• {safe_text(item)}", styles["BulletPoint"]))
        elif isinstance(education, str):
            story.append(Paragraph(safe_text(education), styles["ResumeBody"]))

    # --- Projects ---
    projects = resume_data.get("projects")
    if projects:
        add_section_header("PROJECTS")
        if isinstance(projects, list):
            for proj in projects:
                if isinstance(proj, dict):
                    proj_block = []
                    p_name = safe_text(proj.get("name", "Project"))

                    # Format technologies properly without Python list syntax
                    techs = proj.get("technologies", [])
                    if isinstance(techs, list):
                        tech_str = ", ".join(safe_text(t) for t in techs if t)
                    else:
                        tech_str = safe_text(techs)

                    title_html = f"<b>{p_name}</b>"
                    if tech_str:
                        title_html += f" &nbsp;|&nbsp; <font color='#4B5563'><i>{tech_str}</i></font>"
                    proj_block.append(Paragraph(title_html, styles["ItemTitle"]))

                    # Format bullets cleanly
                    bullets = split_into_bullets(proj.get("description", ""))
                    for b in bullets:
                        b_safe = safe_text(b)
                        proj_block.append(Paragraph(f"&bull;&nbsp; {b_safe}", styles["BulletPoint"]))

                    story.append(KeepTogether(proj_block))
                else:
                    story.append(Paragraph(f"&bull;&nbsp; {safe_text(proj)}", styles["BulletPoint"]))
        elif isinstance(projects, str):
            story.append(Paragraph(safe_text(projects), styles["ResumeBody"]))

    # --- Experience ---
    experience = resume_data.get("experience")
    if experience:
        add_section_header("EXPERIENCE & INTERNSHIPS")
        if isinstance(experience, list):
            for exp in experience:
                if isinstance(exp, dict):
                    exp_block = []
                    role = safe_text(exp.get("role", ""))
                    company = safe_text(exp.get("company", ""))
                    location = safe_text(exp.get("location", ""))
                    dates = safe_text(exp.get("dates", ""))

                    header_parts = []
                    if role:
                        header_parts.append(f"<b>{role}</b>")
                    if company:
                        header_parts.append(company)
                    line1 = " &mdash; ".join(header_parts)
                    if location:
                        line1 += f" ({location})"

                    if line1:
                        exp_block.append(Paragraph(line1, styles["ItemTitle"]))
                    if dates:
                        exp_block.append(Paragraph(dates, styles["ItemSub"]))

                    bullets = split_into_bullets(exp.get("description", ""))
                    for b in bullets:
                        exp_block.append(Paragraph(f"&bull;&nbsp; {safe_text(b)}", styles["BulletPoint"]))

                    story.append(KeepTogether(exp_block))
                else:
                    story.append(Paragraph(f"&bull;&nbsp; {safe_text(exp)}", styles["BulletPoint"]))
        elif isinstance(experience, str):
            story.append(Paragraph(safe_text(experience), styles["ResumeBody"]))

    # --- Certifications & Achievements ---
    certifications = resume_data.get("certifications")
    if certifications:
        add_section_header("CERTIFICATIONS & ACHIEVEMENTS")
        if isinstance(certifications, list):
            for cert in certifications:
                if isinstance(cert, dict):
                    parts = [safe_text(v) for v in cert.values() if v]
                    c_text = " &mdash; ".join(parts)
                else:
                    c_text = safe_text(cert)
                story.append(Paragraph(f"&bull;&nbsp; {c_text}", styles["BulletPoint"]))
        elif isinstance(certifications, str):
            story.append(Paragraph(safe_text(certifications), styles["ResumeBody"]))

    document.build(story)
    return str(output_file)
