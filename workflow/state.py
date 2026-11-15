from typing import Any, Optional, TypedDict


class AgentHireState(TypedDict, total=False):
    # Input
    pdf_path: str
    job_description: str
    session_id: str

    # Parsed resume
    extracted_text: str
    resume_data: dict[str, Any]

    # Evaluations
    evaluation: dict[str, Any]
    updated_evaluation: dict[str, Any]
    initial_score: int
    score_delta: int
    score_explanation: str

    # One canonical list for skill gaps
    skill_gaps: list[str]
    excluded_skill_candidates: list[dict[str, str]]

    # Internal confirmation workflow
    unconfirmed_skills: list[str]
    confirmed_skills: list[str]
    pending_confirmation: bool

    # Optimization
    optimized_data: dict[str, Any]
    final_resume_data: dict[str, Any]

    # Workflow status
    score: int
    iteration: int
    threshold: int
    status: str
    message: str

    # Output
    final_resume_path: str
    error: Optional[str]
