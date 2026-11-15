
import json
from services.llm_service import get_llm


class ResumeParser:
    def __init__(self):
        self.llm = get_llm()

    def parse_resume(self, resume_text: str) -> dict:
        prompt = f"""
You are a resume parsing agent. Return a valid JSON object only.

Use exactly this structure:
{{
    "name": "",
    "email": "",
    "phone": "",
    "summary": "",
    "education": [],
    "skills": [],
    "projects": [],
    "experience": [],
    "certifications": []
}}

Rules:
1. Extract only facts explicitly supported by the resume.
2. Do not invent skills, dates, qualifications, or achievements.
3. Use empty strings or empty lists for missing information.
4. Keep education, projects, and experience as structured lists.
5. Do not include Markdown, explanations, or code fences.
6. Do not reproduce the original resume text in the response.

Resume text:
{resume_text}
"""

        response = self.llm.invoke(
            prompt,
            response_format={"type": "json_object"},
        )

        result = response.content

        if not isinstance(result, str):
            raise ValueError(
                "The LLM returned an unexpected response format."
            )

        try:
            resume_data = json.loads(result)
        except json.JSONDecodeError as exc:
            print("Invalid JSON response from LLM:")
            print(result)
            raise ValueError(
                f"The LLM returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(resume_data, dict):
            raise ValueError("The parsed resume must be a JSON object.")

        list_fields = [
            "education", "skills", "projects",
            "experience", "certifications",
        ]
        string_fields = ["name", "email", "phone", "summary"]

        for field in list_fields:
            if field not in resume_data:
                resume_data[field] = []
            elif not isinstance(resume_data[field], list):
                raise ValueError(
                    f"Invalid resume field: {field} must be a list."
                )

        for field in string_fields:
            if field not in resume_data:
                resume_data[field] = ""
            elif not isinstance(resume_data[field], str):
                raise ValueError(
                    f"Invalid resume field: {field} must be a string."
                )

        resume_data["original_text"] = resume_text
        return resume_data
