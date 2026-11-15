import json
import re
from pathlib import Path
from typing import Any

from services.llm_service import get_llm


class ResumeOptimizer:
    MAX_RETRIES = 2

    FABRICATION_WATCHLIST = {
        "OpenAI", "Azure", "Azure OpenAI", "Azure AI Foundry",
        "React", "React.js", "pytest", "Google Cloud", "GCP",
        "Terraform", "Vertex AI", "AWS", "Kubernetes", "Docker",
        "LangGraph", "LangChain", "tool calling",
        "multi-agent orchestration", "FastAPI", "PostgreSQL",
        "pgvector", "TypeScript", "Python", "Groq", "ChromaDB",
        "FAISS", "TensorFlow", "PyTorch", "MongoDB", "Redis",
        "SQLAlchemy", "Pandas", "NumPy",
    }

    CORE_JD_TERMS = [
        "tool calling",
        "function calling",
        "multi-agent orchestration",
        "multi-agent systems",
        "agentic workflows",
        "LLM agents",
        "retrieval augmented generation",
        "RAG",
        "vector databases",
        "prompt engineering",
        "evaluation pipelines",
        "API integration",
        "Azure OpenAI",
        "Azure AI Foundry",
        "Google Cloud",
        "Vertex AI",
        "Terraform",
        "Kubernetes",
        "pgvector",
        "pytest",
        "React",
        "TypeScript",
    ]

    def __init__(self):
        self.llm = get_llm()

    @staticmethod
    def normalize_text(text: str) -> str:
        if not isinstance(text, str):
            return ""

        for dash in (
            "\u2010", "\u2011", "\u2012", "\u2013",
            "\u2014", "\u2015", "\u2212",
        ):
            text = text.replace(dash, "-")

        return re.sub(r"\s+", " ", text).strip().casefold()

    @classmethod
    def _normalise(cls, text: str) -> str:
        """Compatibility alias for existing workflow code."""
        return cls.normalize_text(text)

    @classmethod
    def _contains_term(cls, text: str, term: str) -> bool:
        """Match a complete term or phrase, not a chopped substring."""
        text_norm = cls.normalize_text(text)
        term_norm = cls.normalize_text(term)

        if not text_norm or not term_norm:
            return False

        if text_norm == term_norm:
            return True

        words = re.findall(r"[a-z0-9+#.]+", term_norm)
        if not words:
            return False

        phrase = r"[\s./_-]+".join(re.escape(word) for word in words)
        pattern = r"(?<![a-z0-9])" + phrase + r"(?![a-z0-9])"

        return re.search(pattern, text_norm, flags=re.IGNORECASE) is not None

    @staticmethod
    def normalize_text_for_display(text: str) -> str:
        for dash in (
            "\u2010", "\u2011", "\u2012", "\u2013",
            "\u2014", "\u2015", "\u2212",
        ):
            text = text.replace(dash, "-")

        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def split_combined_skills(cls, skills: list) -> list[str]:
        """Split combined skill labels and remove normalized duplicates."""
        if not isinstance(skills, list):
            return []

        result = []
        seen = set()

        for raw in skills:
            if not isinstance(raw, str) or not raw.strip():
                continue

            # Split common combined labels without splitting every slash.
            parts = re.split(
                r"\s*(?:\||;|,\s*|\s+/\s+)\s*",
                raw.strip(),
            )

            for part in parts:
                item = cls.normalize_text_for_display(part)
                key = cls.normalize_text(item)

                if item and key not in seen:
                    seen.add(key)
                    result.append(item)

        return result

    @staticmethod
    def _flatten(value: Any) -> str:
        """Flatten resume structures into searchable text."""
        if isinstance(value, dict):
            return " ".join(
                f"{key} {ResumeOptimizer._flatten(item)}"
                for key, item in value.items()
                if key != "original_text"
            )

        if isinstance(value, (list, tuple)):
            return " ".join(
                ResumeOptimizer._flatten(item) for item in value
            )

        if value is None:
            return ""

        return str(value)

    @classmethod
    def _resume_evidence_text(cls, resume_data: dict | None) -> str:
        """Include parsed fields and original resume text when available."""
        if not isinstance(resume_data, dict):
            return ""

        parts = [cls._flatten(resume_data)]
        original_text = resume_data.get("original_text", "")

        if isinstance(original_text, str):
            parts.append(original_text)

        return " ".join(parts)

    @classmethod
    def snap_to_jd(
        cls,
        skills: list,
        job_description: str,
        resume_data: dict | None = None,
    ) -> tuple[list[str], list[dict[str, str]]]:
        """
        Retain complete JD terms that are not already present in the resume.
        Exclusion diagnostics remain internal and are not returned by the API.
        """
        jd = job_description or ""
        resume_text = cls._resume_evidence_text(resume_data)
        accepted = []
        excluded = []
        seen = set()

        for skill in cls.split_combined_skills(skills):
            key = cls.normalize_text(skill)

            if not key or key in seen:
                continue
            seen.add(key)

            if not cls._contains_term(jd, skill):
                excluded.append({
                    "skill": skill,
                    "reason": (
                        "Not found as a complete term in the job description."
                    ),
                })
                continue

            if cls._has_equivalent_resume_evidence(resume_text, skill):
                excluded.append({
                    "skill": skill,
                    "reason": (
                        "Already evidenced in the source resume or by "
                        "an accepted equivalent term."
                    ),
                })
                continue

            accepted.append(skill)

        return accepted, excluded

    @classmethod
    def _has_equivalent_resume_evidence(
        cls,
        resume_text: str,
        skill: str,
    ) -> bool:
        """Apply only explicit, conservative skill-equivalence rules."""
        equivalents = [
            {"multi-agent orchestration", "multi-agent systems"},
            {"tool calling", "function calling"},
            {"retrieval augmented generation", "rag"},
            {"google cloud", "gcp"},
            {"react", "react.js"},
            {"typescript", "type script"},
            {"postgresql", "postgres"},
        ]

        normalized_skill = cls.normalize_text(skill)

        for group in equivalents:
            normalized_group = {
                cls.normalize_text(item) for item in group
            }

            if normalized_skill in normalized_group:
                return any(
                    cls._contains_term(resume_text, alias)
                    for alias in group
                )

        return cls._contains_term(resume_text, skill)

    @classmethod
    def build_skill_gaps(
        cls,
        resume_data: dict,
        job_description: str,
        evaluation: dict,
    ) -> tuple[list[str], list[dict[str, str]]]:
        """
        Build one canonical list internally from evaluator candidates and
        relevant complete phrases found in the JD.
        """
        resume_text = cls._resume_evidence_text(resume_data)
        jd = job_description or ""
        evaluation = evaluation if isinstance(evaluation, dict) else {}

        candidates = []

        for field in ("missing_skills", "keyword_gaps", "skill_gaps"):
            value = evaluation.get(field, [])
            if isinstance(value, list):
                candidates.extend(value)

        # Recover important JD terms that the evaluator might have omitted.
        for term in cls.CORE_JD_TERMS:
            if cls._contains_term(jd, term):
                candidates.append(term)

        candidates = cls.split_combined_skills(candidates)

        canonical = []
        excluded = []
        seen = set()

        for skill in candidates:
            skill = cls.normalize_text_for_display(skill)
            key = cls.normalize_text(skill)

            if not key or key in seen:
                continue
            seen.add(key)

            if not cls._contains_term(jd, skill):
                excluded.append({
                    "skill": skill,
                    "reason": (
                        "Not present as a complete phrase in the job description."
                    ),
                })
                continue

            if cls._has_equivalent_resume_evidence(resume_text, skill):
                excluded.append({
                    "skill": skill,
                    "reason": (
                        "Already evidenced in the resume or by an equivalent term."
                    ),
                })
                continue

            canonical.append(skill)

        return canonical, excluded

    @classmethod
    def normalize_evaluation_gaps(
        cls,
        resume_data: dict,
        job_description: str,
        evaluation: dict,
    ) -> dict:
        """
        Attach internal canonical gaps and diagnostic exclusions.
        The API layer must remove these fields from public evaluations.
        """
        normalized = dict(evaluation or {})

        gaps, excluded = cls.build_skill_gaps(
            resume_data,
            job_description,
            normalized,
        )

        normalized["skill_gaps"] = gaps
        normalized["excluded_skill_candidates"] = excluded

        return normalized

    @classmethod
    def get_unconfirmed_skills(
        cls,
        resume_data: dict,
        evaluation: dict,
        job_description: str | None = None,
    ) -> list[str]:
        """Return the same canonical list that the API presents to the user."""
        if isinstance(evaluation, dict) and isinstance(
            evaluation.get("skill_gaps"), list
        ):
            return cls.split_combined_skills(evaluation["skill_gaps"])

        if not job_description:
            return []

        gaps, _ = cls.build_skill_gaps(
            resume_data,
            job_description,
            evaluation or {},
        )

        return gaps

    @classmethod
    def _contains_phrase(cls, text: str, phrase: str) -> bool:
        return cls._contains_term(text, phrase)

    @classmethod
    def _extract_watchlist_terms(cls, text: str) -> set[str]:
        return {
            cls.normalize_text(term)
            for term in cls.FABRICATION_WATCHLIST
            if cls._contains_term(text, term)
        }

    @classmethod
    def _find_unsupported_watchlist_terms(
        cls,
        source_resume: dict,
        optimized_resume: dict,
        confirmed_skills: list[str] | None = None,
    ) -> list[str]:
        """
        A confirmed skill may be added to the skills array only.
        It cannot be used to invent project, employment, or achievement claims.
        """
        source_text = cls._resume_evidence_text(source_resume)
        skills_text = cls._flatten(optimized_resume.get("skills", []))

        non_skill_data = {
            key: value
            for key, value in optimized_resume.items()
            if key not in {"skills", "original_text"}
        }
        non_skill_text = cls._flatten(non_skill_data)

        output_text = cls._flatten({
            key: value
            for key, value in optimized_resume.items()
            if key != "original_text"
        })

        confirmed = {
            cls.normalize_text(item)
            for item in (confirmed_skills or [])
            if isinstance(item, str)
        }

        violations = []

        for term in sorted(cls.FABRICATION_WATCHLIST, key=str.casefold):
            if not cls._contains_term(output_text, term):
                continue

            if cls._contains_term(source_text, term):
                continue

            confirmed_match = any(
                cls.normalize_text(term) == item
                or cls._contains_term(item, term)
                for item in confirmed
            )

            if (
                confirmed_match
                and cls._contains_term(skills_text, term)
                and not cls._contains_term(non_skill_text, term)
            ):
                continue

            violations.append(term)

        return violations

    @staticmethod
    def _clean_json_response(content: Any) -> dict:
        if not isinstance(content, str):
            raise ValueError("Optimizer returned a non-text response.")

        text = content.strip()

        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            # Fallback extraction of outermost {...}
            match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            raise ValueError(
                "Optimizer did not return valid JSON."
            ) from exc

        if not isinstance(result, dict):
            raise ValueError("Optimizer response must be a JSON object.")

        return result

    def optimize_resume(
        self,
        resume_data: dict,
        job_description: str,
        evaluation: dict,
        confirmed_skills: list[str] | None = None,
    ) -> dict:
        if not isinstance(resume_data, dict) or not resume_data:
            raise ValueError("Valid resume JSON is required.")

        if (
            not isinstance(job_description, str)
            or not job_description.strip()
        ):
            raise ValueError("Job description cannot be empty.")

        if not isinstance(evaluation, dict):
            raise ValueError("Evaluation feedback is required.")

        confirmed_skills = confirmed_skills or []

        if any(
            not isinstance(item, str) or not item.strip()
            for item in confirmed_skills
        ):
            raise ValueError(
                "confirmed_skills must contain non-empty strings."
            )

        normalized_evaluation = self.normalize_evaluation_gaps(
            resume_data,
            job_description,
            evaluation,
        )

        allowed = {
            self.normalize_text(skill)
            for skill in normalized_evaluation["skill_gaps"]
        }

        invalid = [
            skill
            for skill in confirmed_skills
            if self.normalize_text(skill) not in allowed
        ]

        if invalid:
            raise ValueError(
                "Skills were not included in the confirmation list: "
                + ", ".join(invalid)
            )

        # Preserve canonical display forms and remove duplicate confirmations.
        canonical_lookup = {
            self.normalize_text(skill): skill
            for skill in normalized_evaluation["skill_gaps"]
        }

        confirmed_skills = list(dict.fromkeys(
            canonical_lookup[self.normalize_text(skill)]
            for skill in confirmed_skills
        ))

        immutable_fields = [
            "name",
            "email",
            "phone",
            "education",
            "experience",
            "certifications",
            "original_text",
        ]

        # Clean source without original_text clutter to preserve token budget
        clean_source = {k: v for k, v in resume_data.items() if k != "original_text"}

        previous_violations = []

        for _attempt in range(self.MAX_RETRIES + 1):
            prompt = f"""
You are a conservative resume editor. Improve wording, keyword prominence, and ATS alignment
without inventing qualifications, tools, or experience.

SOURCE RESUME JSON:
{json.dumps(clean_source, ensure_ascii=False, indent=2)}

JOB DESCRIPTION (context only, NOT evidence of candidate experience):
{job_description}

EVALUATION:
{json.dumps(normalized_evaluation, ensure_ascii=False, indent=2)}

SKILLS THE USER EXPLICITLY CONFIRMED:
{json.dumps(confirmed_skills, ensure_ascii=False)}

VALIDATION ISSUES FROM YOUR PREVIOUS ATTEMPT:
{json.dumps(previous_violations, ensure_ascii=False)}

Return a valid JSON object with exactly these fields:
{{
  "name": "{resume_data.get('name', '')}",
  "email": "{resume_data.get('email', '')}",
  "phone": "{resume_data.get('phone', '')}",
  "summary": "enhanced professional summary highlighting relevant verified experience",
  "education": {json.dumps(resume_data.get('education', []))},
  "skills": [],
  "projects": [],
  "experience": {json.dumps(resume_data.get('experience', []))},
  "certifications": {json.dumps(resume_data.get('certifications', []))}
}}

Rules:
1. Preserve source facts, dates, contact information, education, jobs,
   certifications, projects, URLs, numbers, and achievements.
2. Never copy a JD requirement into the resume merely because it is required.
3. Confirmed skills may be added to the skills array only.
4. Do not invent project use, employment experience, or achievements for
   confirmed skills.
5. Do not infer PostgreSQL/pgvector from SQLite or one technology from an
   unrelated technology.
6. Do not invent employers, institutions, tools, qualifications, or metrics.
7. Do not add skills the user did not confirm unless they already appear
   in the source resume.
8. Return JSON only, with no Markdown fences.
"""

            try:
                response = self.llm.invoke(
                    prompt,
                    response_format={"type": "json_object"},
                )
                optimized = self._clean_json_response(response.content)
            except Exception as exc:
                previous_violations = [f"JSON generation or parsing error: {exc}"]
                continue

            # Ensure required fields are present
            required_fields = ["summary", "skills", "projects"]
            if not all(k in optimized for k in required_fields):
                previous_violations = ["Missing one of required fields: summary, skills, projects"]
                continue

            # Preserve source-of-truth fields instead of trusting LLM rewrites
            for field in immutable_fields:
                if field in resume_data:
                    optimized[field] = resume_data[field]
                else:
                    optimized.pop(field, None)

            violations = self._find_unsupported_watchlist_terms(
                resume_data,
                optimized,
                confirmed_skills,
            )

            if violations:
                previous_violations = [
                    f"Unsupported technology claim: {item}"
                    for item in violations
                ]
                continue

            try:
                from services.storage_service import JSON_DIR
                output_file = JSON_DIR / "optimized_resume.json"
                with output_file.open("w", encoding="utf-8") as file:
                    json.dump(
                        optimized,
                        file,
                        ensure_ascii=False,
                        indent=2,
                    )
            except Exception as e:
                # Non-fatal caching error
                pass

            return optimized

        raise ValueError(
            "Resume optimization rejected because unsupported claims "
            f"remained after retries: {previous_violations}"
        )
