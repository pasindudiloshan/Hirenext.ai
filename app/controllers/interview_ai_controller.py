# app/controllers/interview_ai_controller.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from flask import Blueprint, current_app, request, jsonify, render_template

from app.services.question_bank_service import QuestionBankService
from app.services.stt_service import STTService
from app.services.evaluator_service import EvaluatorService

# Option B is optional
try:
    from app.services.interview_ai_model_service import InterviewAIModelService  # type: ignore
except Exception:
    InterviewAIModelService = None  # type: ignore


interview_ai_bp = Blueprint("interview_ai_bp", __name__, url_prefix="/interview-ai")


def _db():
    return current_app.mongo.db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if isinstance(x, bool):
            return default
        return float(x)
    except Exception:
        return default


def _ensure_attempt_doc(interview_id: str, role: str) -> Dict[str, Any]:
    """
    Ensure an interview_attempts doc exists for this scheduled interview.
    We use: session_id == interview_id (scheduled interview _id).

    Uses upsert for safety.
    """
    coll = _db().interview_attempts

    base = {
        "session_id": interview_id,
        "interview_id": interview_id,
        "role": role,
        "created_at": _now_iso(),
        "answers": [],
        "final_score": None,   # aggregate 0-10
        "summary": None,
        "status": "IN_PROGRESS",
    }

    coll.update_one(
        {"session_id": interview_id},
        {"$setOnInsert": base},
        upsert=True
    )

    return coll.find_one({"session_id": interview_id}) or base


def _merge_final_score(answers: List[Dict[str, Any]]) -> float:
    """Mean of per-question final_score_0_10."""
    scores: List[float] = []
    for a in answers or []:
        v = a.get("final_score_0_10")
        if isinstance(v, (int, float)):
            scores.append(float(v))
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 2)


def _upsert_answer(session_id: str, question_id: str, row: Dict[str, Any]) -> None:
    """
    Avoid duplicates: if re-submit for same question_id, overwrite.
    """
    coll = _db().interview_attempts

    # Ensure parent doc exists
    coll.update_one(
        {"session_id": session_id},
        {"$setOnInsert": {"session_id": session_id, "created_at": _now_iso(), "answers": []}},
        upsert=True
    )

    # Replace existing answer for this question
    res = coll.update_one(
        {"session_id": session_id, "answers.question_id": question_id},
        {"$set": {"answers.$": row}},
    )
    if res.matched_count:
        return

    # Else push as new
    coll.update_one(
        {"session_id": session_id},
        {"$push": {"answers": row}},
    )


def _compute_hybrid_score(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[float, str]:
    """
    Returns (final_score_0_10, mode_used)
    Modes:
      - A_ONLY
      - HYBRID (A + B blend)
    """
    mode_cfg = str(current_app.config.get("AI_SCORING_MODE") or "HYBRID").strip().upper()

    a_score = _safe_float(a.get("rubric_score", 0), 0.0)
    final_0_10 = a_score
    mode_used = "A_ONLY"

    if mode_cfg != "A_ONLY" and isinstance(b.get("score_0_10"), (int, float)):
        # Blend weights (tweak anytime)
        final_0_10 = round(0.65 * a_score + 0.35 * float(b["score_0_10"]), 2)
        mode_used = "HYBRID"

    return final_0_10, mode_used


@interview_ai_bp.route("/submit-answer", methods=["POST"])
def submit_answer():
    """
    Called from interview.html JS.

    multipart/form-data:
      - interview_id
      - role
      - question_id
      - audio

    NEW behavior for your desired UX:
      ✅ We still SAVE full breakdown to Mongo for the Results page
      ✅ But we RETURN minimal JSON (fast + no “matched/missing” during interview)
    """
    interview_id = (request.form.get("interview_id") or "").strip()
    role = (request.form.get("role") or "").strip()
    question_id = (request.form.get("question_id") or "").strip()
    audio = request.files.get("audio")

    if not (interview_id and role and question_id and audio):
        return jsonify({"ok": False, "error": "Missing interview_id/role/question_id/audio"}), 400

    # Ensure attempt doc exists
    doc = _ensure_attempt_doc(interview_id=interview_id, role=role)

    # Trust DB role if exists (prevents spoofing)
    db_role = str(doc.get("role") or "").strip()
    if db_role and role != db_role:
        role = db_role

    # Load question
    q = QuestionBankService.get_question(role, question_id)
    if not q:
        return jsonify({"ok": False, "error": f"Question not found for role '{role}'"}), 404

    # 1) STT
    transcript, stt_meta = STTService.transcribe(audio)

    # 2) Option A scoring (full breakdown for DB)
    a = EvaluatorService.evaluate_answer(question=q, answer_text=transcript)

    # 3) Option B scoring (optional)
    b: Dict[str, Any] = {}
    if InterviewAIModelService is not None:
        try:
            b = InterviewAIModelService.score_answer(transcript) or {}
        except Exception as e:
            b = {"error": str(e)}

    # 4) Hybrid final score
    final_0_10, mode_used = _compute_hybrid_score(a=a, b=b)

    # 5) Save full row (for Results page)
    row: Dict[str, Any] = {
        "question_id": question_id,
        "transcript": transcript,

        # Option A (full)
        "rubric_score": a.get("rubric_score", 0),
        "concept_correct": a.get("concept_correct", False),
        "awarded_points": a.get("awarded_points", []),
        "missed_points": a.get("missed_points", []),
        "rubric_details": a.get("rubric_details", []),
        "concept_details": a.get("concept_details", {}),
        "red_flags_triggered": a.get("red_flags_triggered", []),
        "feedback": a.get("feedback", ""),

        # Option B (optional)
        "model_label": b.get("label"),
        "model_quality": b.get("quality"),
        "model_score_0_10": b.get("score_0_10"),
        "model_error": b.get("error"),

        # Final
        "final_score_0_10": final_0_10,
        "mode_used": mode_used,

        # STT metadata
        "stt_meta": stt_meta if isinstance(stt_meta, dict) else getattr(stt_meta, "to_dict", lambda: stt_meta)(),

        "created_at": _now_iso(),
    }

    _upsert_answer(session_id=interview_id, question_id=question_id, row=row)

    # 6) Update aggregate score
    updated = _db().interview_attempts.find_one({"session_id": interview_id}) or {}
    answers: List[Dict[str, Any]] = updated.get("answers") or []
    avg = _merge_final_score(answers)

    _db().interview_attempts.update_one(
        {"session_id": interview_id},
        {"$set": {"final_score": avg, "updated_at": _now_iso()}}
    )

    # 7) RETURN MINIMAL RESPONSE (for new interview UX)
    #    (Your updated interview.js will auto-next; no breakdown UI needed)
    return jsonify({
        "ok": True,
        "interview_id": interview_id,
        "role": role,
        "question_id": question_id,
        "transcript": transcript,
        "final_overall_0_10": avg,
    })


@interview_ai_bp.route("/results/<interview_id>", methods=["GET"])
def results(interview_id: str):
    """
    Results page for a scheduled interview.
    Shows ALL breakdown saved per question.
    """
    doc = _db().interview_attempts.find_one({"session_id": interview_id}) or {}
    answers: List[Dict[str, Any]] = doc.get("answers") or []

    avg = _merge_final_score(answers)

    _db().interview_attempts.update_one(
        {"session_id": interview_id},
        {"$set": {"final_score": avg, "status": "COMPLETED", "completed_at": _now_iso()}}
    )

    # ✅ FIXED TEMPLATE PATH (your uploaded template is interview_ai/interview_results.html)
    return render_template("feedback/interview_results.html", doc=doc, final_score=avg)