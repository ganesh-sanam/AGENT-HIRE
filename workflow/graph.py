from pathlib import Path
from uuid import uuid4

from langgraph.graph import StateGraph, END

from workflow.state import AgentHireState
from agents.resume_parser import ResumeParser
from agents.resume_evaluator import ResumeEvaluator
from agents.resume_optimizer import ResumeOptimizer
from services.pdf_service import extract_text_from_pdf
from services.resume_output_service import generate_resume_pdf


parser = ResumeParser()
evaluator = ResumeEvaluator()
optimizer = ResumeOptimizer()

DEFAULT_THRESHOLD = 80
from services.storage_service import BASE_DIR, OUTPUT_DIR


def normalize_pdf_text(value):
    """Normalize unsupported Unicode dashes before PDF generation."""
    if isinstance(value, str):
        for dash in (
            "\u2010", "\u2011", "\u2012", "\u2013",
            "\u2014", "\u2015", "\u2212",
        ):
            value = value.replace(dash, "-")
        return value

    if isinstance(value, list):
        return [normalize_pdf_text(item) for item in value]

    if isinstance(value, tuple):
        return tuple(normalize_pdf_text(item) for item in value)

    if isinstance(value, dict):
        return {
            normalize_pdf_text(key) if isinstance(key, str) else key:
            normalize_pdf_text(item)
            for key, item in value.items()
        }

    return value


def analyze_parse(state: AgentHireState) -> dict:
    text = extract_text_from_pdf(state["pdf_path"])
    resume_data = parser.parse_resume(text)

    return {
        "extracted_text": text,
        "resume_data": resume_data,
        "iteration": 0,
        "threshold": state.get("threshold", DEFAULT_THRESHOLD),
        "status": "processing",
    }


def analyze_evaluate(state: AgentHireState) -> dict:
    evaluation = evaluator.evaluate_resume(
        resume_data=state["resume_data"],
        job_description=state["job_description"],
    )

    if evaluation.get("status") == "insufficient_jd":
        return {
            "evaluation": evaluation,
            "score": 0,
            "initial_score": 0,
            "status": "insufficient_jd",
            "skill_gaps": [],
            "unconfirmed_skills": [],
            "excluded_skill_candidates": [],
            "pending_confirmation": False,
            "message": evaluation.get(
                "reasoning",
                "Please provide a more detailed job description.",
            ),
        }

    evaluation = optimizer.normalize_evaluation_gaps(
        state["resume_data"],
        state["job_description"],
        evaluation,
    )

    skill_gaps = evaluation.get("skill_gaps", [])
    initial_score = evaluation.get("score", 0)

    return {
        "evaluation": evaluation,
        "score": initial_score,
        "initial_score": initial_score,
        "status": (
            "pending_confirmation" if skill_gaps
            else "ready_to_optimize"
        ),
        "skill_gaps": skill_gaps,
        # Internal alias for existing confirmation workflow.
        "unconfirmed_skills": skill_gaps,
        "excluded_skill_candidates": evaluation.get(
            "excluded_skill_candidates", []
        ),
        "pending_confirmation": bool(skill_gaps),
        "message": (
            "Review the skill gaps and confirm only skills you genuinely possess."
            if skill_gaps
            else "No additional skill confirmation is required."
        ),
    }


analysis = StateGraph(AgentHireState)
analysis.add_node("parse", analyze_parse)
analysis.add_node("evaluate", analyze_evaluate)
analysis.set_entry_point("parse")
analysis.add_edge("parse", "evaluate")
analysis.add_edge("evaluate", END)
analysis_graph = analysis.compile()


def optimize_node(state: AgentHireState) -> dict:
    optimized = optimizer.optimize_resume(
        resume_data=state["resume_data"],
        job_description=state["job_description"],
        evaluation=state["evaluation"],
        confirmed_skills=state.get("confirmed_skills", []),
    )

    return {
        "optimized_data": normalize_pdf_text(optimized),
        "iteration": state.get("iteration", 0) + 1,
    }


def evaluate_optimized_node(state: AgentHireState) -> dict:
    evaluation = evaluator.evaluate_resume(
        resume_data=state["optimized_data"],
        job_description=state["job_description"],
    )

    score = evaluation.get("score", 0)
    initial_score = state.get("initial_score", state.get("score", score))
    score_delta = score - initial_score
    confirmed = state.get("confirmed_skills", [])

    if score_delta > 0:
        if confirmed:
            explanation = (
                f"Score increased by {score_delta} points ({initial_score} -> {score}). "
                f"Improvement reflects {len(confirmed)} confirmed skill(s) integrated into your profile "
                f"and enhanced ATS keyword alignment of existing verified experience."
            )
        else:
            explanation = (
                f"Score increased by {score_delta} points ({initial_score} -> {score}). "
                f"No unconfirmed skills were added. Improvement is driven by "
                f"clearer ATS phrasing, prominent keyword organization, and refined presentation "
                f"of your existing verified experience."
            )
    elif score_delta < 0:
        explanation = (
            f"Score adjusted from {initial_score} to {score}. Profile was conservatively optimized "
            f"to strictly avoid unsupported claims."
        )
    else:
        explanation = (
            f"Score remains {score}/100. Resume structure, formatting, and ATS clarity were enhanced "
            f"while preserving exact factual content."
        )

    return {
        "updated_evaluation": evaluation,
        "score": score,
        "initial_score": initial_score,
        "score_delta": score_delta,
        "score_explanation": explanation,
        "threshold": state.get("threshold", DEFAULT_THRESHOLD),
        "final_resume_data": normalize_pdf_text(state["optimized_data"]),
        "status": "completed",
        "message": (
            f"Resume optimization completed. Score: {score}/100. "
            f"{explanation} (Score is informational only)."
        ),
    }


def make_pdf(state: AgentHireState) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session_id = state.get("session_id") or uuid4().hex
    output_path = OUTPUT_DIR / f"optimized_resume_{session_id}.pdf"

    pdf_ready_data = normalize_pdf_text(state["final_resume_data"])
    generated_path = generate_resume_pdf(
        resume_data=pdf_ready_data,
        output_path=str(output_path),
    )

    return {
        "final_resume_path": str(generated_path),
        "status": "completed",
    }


optimization = StateGraph(AgentHireState)
optimization.add_node("optimize", optimize_node)
optimization.add_node("evaluate", evaluate_optimized_node)
optimization.add_node("make_pdf", make_pdf)

optimization.set_entry_point("optimize")
optimization.add_edge("optimize", "evaluate")
# No score threshold gate: PDF is generated after confirmation.
optimization.add_edge("evaluate", "make_pdf")
optimization.add_edge("make_pdf", END)

optimization_graph = optimization.compile()
