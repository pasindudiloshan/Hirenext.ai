from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import smtplib
from email.message import EmailMessage

from bson import ObjectId
from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    url_for,
    redirect,
)

from app.models.shortlisted_batch_model import ShortlistedBatchModel
from app.services.interview_service import InterviewService
from app.services.question_bank_service import QuestionBankService

interview_bp = Blueprint("interview_bp", __name__)


# ============================================================
# Helpers
# ============================================================

def _iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _oid(val: str) -> Optional[ObjectId]:
    try:
        return ObjectId(val)
    except Exception:
        return None


def _json_safe(value: Any) -> Any:
    """
    Deep-convert Mongo/unserializable values into JSON-safe types.
    Handles nested dicts/lists/tuples/sets, ObjectId, datetime.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    return value


def _batch_shortlisted_count(batch: Dict[str, Any]) -> int:
    cands = batch.get("shortlisted_candidates") or []
    return len(cands)


def _get_db():
    return current_app.mongo.db


def _remaining(shortlisted_count: int, interviews_scheduled: int) -> int:
    try:
        return max(0, int(shortlisted_count) - int(interviews_scheduled))
    except Exception:
        return 0


def _normalize_role(role: str) -> str:
    role = (role or "").strip()
    for suffix in ("(Remote)", "(Onsite)", "(Hybrid)"):
        role = role.replace(suffix, "")
    role = role.split(" - ")[0].strip()
    return role


def _build_interview_email_content(
    candidate_name: str,
    job_role: str,
    meeting_date: str,
    meeting_time: str,
    meeting_link: str,
    company_name: str = "HireNext.ai",
    support_email: str = "support@hirenext.ai",
) -> tuple[str, str, str]:
    """
    Returns: (subject, text_body, html_body)
    """
    candidate_name = candidate_name or "Candidate"
    job_role = job_role or "the selected role"
    meeting_time = meeting_time or "As scheduled"

    subject = f"Interview Invitation – {job_role} at {company_name}"

    text_body = f"""Dear {candidate_name},

Congratulations!

We are pleased to inform you that you have been shortlisted for the next stage of the hiring process for the position of {job_role} at {company_name}.

Your interview has been scheduled with the details below:

Interview Details
-------------------------
Date: {meeting_date}
Time: {meeting_time}
Meeting Link: {meeting_link}
Platform: Online Video Interview
Duration: Approximately 10–15 minutes

Please join the meeting a few minutes before the scheduled time and ensure that your internet connection, camera, and microphone are working properly.

During the interview, you may be asked questions related to your experience, skills, and problem-solving abilities. We encourage you to answer clearly and confidently.

If you face any issues joining the meeting or need to reschedule, please contact us at:
{support_email}

We look forward to speaking with you and learning more about your experience.

Best regards,
Hiring Team
{company_name}
"""

    html_body = f"""
    <html>
      <body style="margin:0; padding:0; background-color:#f5f7fb; font-family:Arial, Helvetica, sans-serif; color:#1f2937;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f5f7fb; padding:24px 0;">
          <tr>
            <td align="center">
              <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="max-width:640px; width:100%; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,0.08);">
                <tr>
                  <td style="background:linear-gradient(135deg,#ff7a18,#ff9f43); padding:28px 32px; color:#ffffff;">
                    <h1 style="margin:0; font-size:26px; line-height:1.3;">Interview Invitation</h1>
                    <p style="margin:8px 0 0; font-size:15px; opacity:0.95;">{company_name}</p>
                  </td>
                </tr>

                <tr>
                  <td style="padding:32px;">
                    <p style="margin:0 0 16px; font-size:16px;">Dear <strong>{candidate_name}</strong>,</p>

                    <p style="margin:0 0 16px; font-size:15px; line-height:1.7;">
                      Congratulations! We are pleased to inform you that you have been shortlisted for the next stage
                      of the hiring process for the position of <strong>{job_role}</strong> at <strong>{company_name}</strong>.
                    </p>

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:24px 0; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
                      <tr>
                        <td colspan="2" style="background:#fff7ed; padding:14px 18px; border-bottom:1px solid #e5e7eb;">
                          <strong style="font-size:16px; color:#9a3412;">Interview Details</strong>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:12px 18px; width:160px; border-bottom:1px solid #e5e7eb;"><strong>Date</strong></td>
                        <td style="padding:12px 18px; border-bottom:1px solid #e5e7eb;">{meeting_date}</td>
                      </tr>
                      <tr>
                        <td style="padding:12px 18px; width:160px; border-bottom:1px solid #e5e7eb;"><strong>Time</strong></td>
                        <td style="padding:12px 18px; border-bottom:1px solid #e5e7eb;">{meeting_time}</td>
                      </tr>
                      <tr>
                        <td style="padding:12px 18px; width:160px; border-bottom:1px solid #e5e7eb;"><strong>Platform</strong></td>
                        <td style="padding:12px 18px; border-bottom:1px solid #e5e7eb;">Online Video Interview</td>
                      </tr>
                      <tr>
                        <td style="padding:12px 18px; width:160px; border-bottom:1px solid #e5e7eb;"><strong>Duration</strong></td>
                        <td style="padding:12px 18px; border-bottom:1px solid #e5e7eb;">Approximately 10–15 minutes</td>
                      </tr>
                      <tr>
                        <td style="padding:12px 18px; width:160px;"><strong>Meeting Link</strong></td>
                        <td style="padding:12px 18px;">
                          <a href="{meeting_link}" style="color:#ea580c; text-decoration:none; word-break:break-all;">{meeting_link}</a>
                        </td>
                      </tr>
                    </table>

                    <p style="margin:0 0 14px; font-size:15px; line-height:1.7;">
                      Please join the meeting a few minutes before the scheduled time and make sure your internet
                      connection, camera, and microphone are working properly.
                    </p>

                    <p style="margin:0 0 14px; font-size:15px; line-height:1.7;">
                      During the interview, you may be asked questions related to your experience, skills, and
                      problem-solving abilities. We encourage you to answer clearly and confidently.
                    </p>

                    <p style="margin:0 0 24px; font-size:15px; line-height:1.7;">
                      If you face any issues joining the meeting or need to reschedule, please contact us at
                      <a href="mailto:{support_email}" style="color:#ea580c; text-decoration:none;">{support_email}</a>.
                    </p>

                    <p style="margin:0; font-size:15px; line-height:1.7;">
                      We look forward to speaking with you and learning more about your experience.
                    </p>

                    <p style="margin:24px 0 0; font-size:15px; line-height:1.7;">
                      Best regards,<br>
                      <strong>Hiring Team</strong><br>
                      {company_name}
                    </p>
                  </td>
                </tr>

                <tr>
                  <td style="padding:18px 32px; background:#f9fafb; border-top:1px solid #e5e7eb; font-size:12px; color:#6b7280; text-align:center;">
                    This is an automated interview invitation from {company_name}.
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    return subject, text_body, html_body


# ============================================================
# Pages
# ============================================================

@interview_bp.route("/calander", methods=["GET"])
def calander_page():
    """
    Calendar UI: shows interviews like Google Calendar.
    Template: templates/interview/calander.html
    """
    now = datetime.now(timezone.utc)
    date_from = (request.args.get("from") or "").strip()
    date_to = (request.args.get("to") or "").strip()
    batch_id = (request.args.get("batch_id") or "").strip()

    if date_from and date_to:
        start = date_from
        end = date_to
    else:
        start = _iso_date(now - timedelta(days=30))
        end = _iso_date(now + timedelta(days=180))

    events = InterviewService.get_calendar_events(
        start_date=start,
        end_date=end,
        batch_id=batch_id or None
    ) or []

    interviews = _json_safe(events)
    return render_template("interview/calander.html", interviews=interviews)


@interview_bp.route("/schedule", methods=["GET"])
def schedule_page():
    """
    Schedule UI
    Template: templates/interview/schedule.html
    """
    db = _get_db()

    batches = list(db.screening_batches.find().sort("created_at", -1))
    batches_ser = [_json_safe(b) for b in batches]

    batch_id = (request.args.get("batch_id") or "").strip()
    active_batch = None

    if batch_id:
        active_batch = ShortlistedBatchModel.get_batch_by_id(batch_id)
    elif batches:
        active_batch = batches[0]

    active_batch_ser = _json_safe(active_batch) if active_batch else {}

    shortlisted_candidates_raw = (active_batch or {}).get("shortlisted_candidates") or []
    shortlisted_candidates = _json_safe(shortlisted_candidates_raw)
    total_shortlisted = len(shortlisted_candidates_raw)

    selected_date_iso = (request.args.get("date") or "").strip()

    recent_interviews: List[Dict[str, Any]] = []
    total_scheduled_for_active_batch = 0

    try:
        if active_batch and active_batch.get("_id"):
            bid = str(active_batch["_id"])

            total_scheduled_for_active_batch = int(
                db.interviews.count_documents({"batch_id": bid}) or 0
            )

            today = _iso_date(datetime.now(timezone.utc))
            future = _iso_date(datetime.now(timezone.utc) + timedelta(days=60))
            recent_interviews = list(
                db.interviews.find({"batch_id": bid, "date": {"$gte": today, "$lte": future}})
                .sort("start_time", 1)
            )
    except Exception:
        recent_interviews = []
        total_scheduled_for_active_batch = 0

    recent_interviews_ser = [_json_safe(x) for x in recent_interviews]
    meeting_link = (active_batch or {}).get("meeting_link_default") or ""

    remaining_to_schedule = _remaining(total_shortlisted, total_scheduled_for_active_batch)

    try:
        counts: Dict[str, int] = {}
        ids = [str(b["_id"]) for b in batches if b.get("_id")]
        if ids:
            pipeline = [
                {"$match": {"batch_id": {"$in": ids}}},
                {"$group": {"_id": "$batch_id", "cnt": {"$sum": 1}}},
            ]
            for row in db.interviews.aggregate(pipeline):
                counts[str(row["_id"])] = int(row.get("cnt", 0))

        for b in batches_ser:
            b_id = str(b.get("_id", ""))
            sc = _batch_shortlisted_count(b)
            ic = counts.get(b_id, 0)

            b["shortlisted_count"] = int(sc)
            b["interviews_scheduled"] = int(ic)
            b["remaining_to_schedule"] = _remaining(sc, ic)

    except Exception:
        for b in batches_ser:
            sc = _batch_shortlisted_count(b)
            b["shortlisted_count"] = int(sc)
            b["interviews_scheduled"] = 0
            b["remaining_to_schedule"] = int(sc)

    selected_date_label = None
    if selected_date_iso:
        try:
            dt = datetime.strptime(selected_date_iso, "%Y-%m-%d")
            selected_date_label = dt.strftime("%d %b %Y")
        except Exception:
            selected_date_label = None

    return render_template(
        "interview/schedule.html",
        batches=batches_ser,
        active_batch=active_batch_ser,
        shortlisted_candidates=shortlisted_candidates,
        total_shortlisted=total_shortlisted,
        total_scheduled=total_scheduled_for_active_batch,
        remaining_to_schedule=remaining_to_schedule,
        recent_interviews=recent_interviews_ser,
        meeting_link=meeting_link,
        selected_date_iso=selected_date_iso,
        selected_date_label=selected_date_label,
        time_slots=[],
    )


@interview_bp.route("/meeting/<interview_id>", methods=["GET"])
def meeting_page(interview_id: str):
    """
    Meeting edit page (opened from calendar day-details popup)
    Template: templates/interview/meeting.html
    The page will load interview details via:
      GET /interview/api/interview/<id>
    """
    return render_template("interview/meeting.html", interview_id=str(interview_id))


# ============================================================
# Interview Preview Page
# ============================================================

@interview_bp.route("/interview_Q/<interview_id>", methods=["GET"])
def interview_preview_page(interview_id: str):
    """
    Middle preview page:
      - Shows role + topics + questions one-by-one
      - After last question shows 3..2..1 then auto-redirects to interview.html
    """
    db = _get_db()
    oid = _oid(interview_id)

    redirect_url = url_for("interview_bp.live_interview_page", interview_id=str(interview_id))

    role = ""
    questions: List[str] = []
    topics: List[str] = []

    if oid:
        row = db.interviews.find_one({"_id": oid}) or {}
        role_raw = (row.get("job_title") or row.get("role") or "").strip()
        role = _normalize_role(role_raw)

        q_full = (QuestionBankService.get_questions_for_role(role) if role else [])[:5]

        for q in (q_full or []):
            if isinstance(q, dict):
                qtext = str(q.get("question") or "").strip()
                if qtext:
                    questions.append(qtext)

                skill = str(q.get("skill") or "").strip()
                if skill:
                    topics.append(skill)

    seen = set()
    topics = [t for t in topics if not (t.lower() in seen or seen.add(t.lower()))]

    if not questions:
        questions = [
            "Preparing your questions…",
            "Checking audio and camera permissions…",
            "Almost ready to start…",
        ]
        if not topics:
            topics = ["General"]

    show_each_ms = 1800
    countdown_sec = 3

    return render_template(
        "interview/interview_Q.html",
        interview_id=str(interview_id),
        role=role or "Interview",
        topics=topics,
        questions=questions,
        redirect_url=redirect_url,
        show_each_ms=show_each_ms,
        countdown_sec=countdown_sec,
    )


# ============================================================
# Live Interview Session Page
# ============================================================

@interview_bp.route("/interview/<interview_id>", methods=["GET"])
def live_interview_page(interview_id: str):
    """
    Live AI interview session page
    Template: templates/interview/interview.html
    This route is used because meeting.html points to:
      /interview/interview/<id>
    """
    db = _get_db()
    oid = _oid(interview_id)

    submit_url = url_for("interview_ai_bp.submit_answer")
    results_url = url_for("interview_ai_bp.results", interview_id=str(interview_id))

    if not oid:
        return render_template(
            "interview/interview.html",
            interview_id=str(interview_id),
            candidate_name="Candidate",
            role="",
            questions=[],
            submit_url=submit_url,
            results_url=results_url,
            end_url=results_url,
        )

    row = db.interviews.find_one({"_id": oid}) or {}

    candidate_name = (
        row.get("candidate_name")
        or row.get("candidate")
        or row.get("name")
        or "Candidate"
    )

    role_raw = (row.get("job_title") or row.get("role") or "").strip()
    role = _normalize_role(role_raw)

    questions_full = (QuestionBankService.get_questions_for_role(role) if role else [])[:5]
    questions: List[Dict[str, Any]] = []
    for q in (questions_full or []):
        if isinstance(q, dict):
            questions.append({
                "id": str(q.get("id", "")).strip(),
                "skill": q.get("skill", ""),
                "difficulty": q.get("difficulty", ""),
                "question": q.get("question", ""),
            })

    try:
        db.interview_attempts.update_one(
            {"session_id": str(interview_id)},
            {"$setOnInsert": {
                "session_id": str(interview_id),
                "interview_id": str(interview_id),
                "batch_id": row.get("batch_id"),
                "candidate_id": row.get("candidate_id"),
                "candidate_name": str(candidate_name),
                "candidate_email": row.get("candidate_email") or row.get("email"),
                "role": role,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "answers": [],
                "final_score": None,
                "summary": None,
                "status": "IN_PROGRESS",
            }},
            upsert=True
        )
    except Exception:
        pass

    return render_template(
        "interview/interview.html",
        interview_id=str(interview_id),
        candidate_name=str(candidate_name),
        role=role,
        questions=questions,
        submit_url=submit_url,
        results_url=results_url,
        end_url=results_url,
    )


# ============================================================
# Mail popup page
# ============================================================

@interview_bp.route("/mail", methods=["GET"])
def mail_page():
    """
    Popup page with form:
      - candidate email
      - meeting link
    Template: templates/interview/mail.html
    """
    meeting_date = (request.args.get("date") or "").strip()
    meeting_link = (request.args.get("link") or "").strip()
    to_email = (request.args.get("email") or "").strip()

    return render_template(
        "interview/mail.html",
        meeting_date=meeting_date,
        meeting_link=meeting_link,
        to_email=to_email,
    )


# ============================================================
# APIs
# ============================================================

@interview_bp.route("/api/day_slots", methods=["GET"])
def api_day_slots():
    batch_id = (request.args.get("batch_id") or "").strip()
    date_iso = (request.args.get("date") or "").strip()
    duration = int((request.args.get("duration") or "10").strip() or 10)
    tz = (request.args.get("tz") or "Asia/Colombo").strip()

    if not batch_id or not date_iso:
        return jsonify({"ok": False, "error": "batch_id and date are required"}), 400

    batch = ShortlistedBatchModel.get_batch_by_id(batch_id)
    if not batch:
        return jsonify({"ok": False, "error": "Batch not found"}), 404

    db = _get_db()
    meeting_link = batch.get("meeting_link_default") or ""

    total_shortlisted = len((batch.get("shortlisted_candidates") or []))
    interviews_scheduled = int(db.interviews.count_documents({"batch_id": str(batch_id)}) or 0)
    remaining_to_schedule = _remaining(total_shortlisted, interviews_scheduled)

    payload = InterviewService.build_slots_with_status(
        batch_id=batch_id,
        date_iso=date_iso,
        duration_min=duration,
        tz=tz,
    )

    return jsonify({
        "ok": True,
        "date": date_iso,
        "duration": duration,
        "tz": tz,
        "meeting_link": meeting_link,
        "total_shortlisted": int(total_shortlisted),
        "interviews_scheduled": int(interviews_scheduled),
        "remaining_to_schedule": int(remaining_to_schedule),
        "slots": _json_safe(payload.get("slots", [])),
        "booked": _json_safe(payload.get("booked", [])),
        "interviews": _json_safe(payload.get("interviews", [])),
    })


@interview_bp.route("/api/batch_interviews", methods=["GET"])
def api_batch_interviews():
    """
    Fetch all interviews for a batch.
    Returns scheduled_candidate_ids so UI can schedule remaining candidates across days.
    Also returns remaining_to_schedule to allow disabling UI.
    """
    db = _get_db()
    batch_id = (request.args.get("batch_id") or "").strip()

    if not batch_id:
        return jsonify({"ok": False, "error": "batch_id is required"}), 400

    batch = ShortlistedBatchModel.get_batch_by_id(batch_id)
    if not batch:
        return jsonify({"ok": False, "error": "Batch not found"}), 404

    try:
        rows = list(
            db.interviews.find({"batch_id": str(batch_id)})
            .sort([("date", 1), ("start_time", 1)])
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"DB read failed: {e}"}), 500

    safe_rows: List[Dict[str, Any]] = []
    scheduled_candidate_ids: List[str] = []

    for r in rows:
        x = _json_safe(dict(r))
        safe_rows.append(x)

        cid = x.get("candidate_id") or ""
        if cid:
            scheduled_candidate_ids.append(str(cid))

    seen = set()
    scheduled_candidate_ids = [c for c in scheduled_candidate_ids if not (c in seen or seen.add(c))]

    total_shortlisted = len((batch.get("shortlisted_candidates") or []))
    interviews_scheduled = len(rows)
    remaining_to_schedule = _remaining(total_shortlisted, interviews_scheduled)

    return jsonify({
        "ok": True,
        "batch_id": str(batch_id),
        "scheduled_candidate_ids": scheduled_candidate_ids,
        "total_shortlisted": int(total_shortlisted),
        "interviews_scheduled": int(interviews_scheduled),
        "remaining_to_schedule": int(remaining_to_schedule),
        "interviews": safe_rows,
    })


@interview_bp.route("/api/schedule", methods=["POST"])
def api_schedule():
    data = request.get_json(silent=True) or {}
    batch_id = _safe_str(data.get("batch_id")).strip()
    date_iso = _safe_str(data.get("date")).strip()
    tz = _safe_str(data.get("tz") or "Asia/Colombo").strip()
    duration = int(data.get("duration") or 10)
    meeting_link = _safe_str(data.get("meeting_link") or "").strip()
    interviews = data.get("interviews") or []

    if not batch_id or not date_iso:
        return jsonify({"ok": False, "error": "batch_id and date are required"}), 400

    batch = ShortlistedBatchModel.get_batch_by_id(batch_id)
    if not batch:
        return jsonify({"ok": False, "error": "Batch not found"}), 404

    if not isinstance(interviews, list) or len(interviews) == 0:
        return jsonify({"ok": False, "error": "No interviews provided"}), 400

    result = InterviewService.save_confirmed_interviews(
        batch_doc=batch,
        date_iso=date_iso,
        tz=tz,
        duration_min=duration,
        meeting_link=meeting_link,
        interviews=interviews,
    )

    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "Failed to save interviews")}), 400

    return jsonify({
        "ok": True,
        "message": "Slots confirmed & saved.",
        "inserted": int(result.get("inserted", 0)),
    })


@interview_bp.route("/api/send_invites", methods=["POST"])
def api_send_invites():
    db = _get_db()

    data = request.get_json(silent=True) or {}
    batch_id = _safe_str(data.get("batch_id")).strip()
    date_iso = _safe_str(data.get("date")).strip()
    interviews = data.get("interviews") or []

    if not batch_id or not date_iso:
        return jsonify({"ok": False, "error": "batch_id and date are required"}), 400

    if not isinstance(interviews, list) or len(interviews) == 0:
        return jsonify({"ok": False, "error": "No interviews provided"}), 400

    emails: List[str] = []
    for it in interviews:
        em = _safe_str(it.get("candidate_email") or it.get("email")).strip()
        if em:
            emails.append(em)

    if not emails:
        return jsonify({"ok": False, "error": "No candidate emails found"}), 400

    try:
        db.interviews.update_many(
            {"batch_id": batch_id, "date": date_iso, "candidate_email": {"$in": emails}},
            {"$set": {"invite_sent": True, "invite_sent_at": datetime.now(timezone.utc)}}
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"DB update failed: {e}"}), 500

    return jsonify({"ok": True, "message": "Invites marked as sent (email service will be added next)."})


@interview_bp.route("/api/calendar_events", methods=["GET"])
def api_calendar_events():
    start = (request.args.get("from") or "").strip()
    end = (request.args.get("to") or "").strip()
    batch_id = (request.args.get("batch_id") or "").strip()

    if not start or not end:
        return jsonify({"ok": False, "error": "from and to are required"}), 400

    events = InterviewService.get_calendar_events(
        start_date=start,
        end_date=end,
        batch_id=batch_id or None
    ) or []

    return jsonify({"ok": True, "events": _json_safe(events)})


# ============================================================
# Send manual email via Gmail SMTP
# ============================================================

@interview_bp.route("/api/send_manual_email", methods=["POST"])
def send_manual_email():
    to_email = (request.form.get("to_email") or "").strip()
    meeting_link = (request.form.get("meeting_link") or "").strip()
    meeting_date = (request.form.get("meeting_date") or "").strip()

    candidate_name = (request.form.get("candidate_name") or "Candidate").strip()
    job_role = (request.form.get("job_role") or "Interview Role").strip()
    meeting_time = (request.form.get("meeting_time") or "As scheduled").strip()

    if not to_email or not meeting_link or not meeting_date:
        return render_template(
            "interview/mail.html",
            error="All fields are required.",
            meeting_date=meeting_date,
            meeting_link=meeting_link,
            to_email=to_email
        ), 400

    smtp_host = current_app.config.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(current_app.config.get("SMTP_PORT", 587))
    smtp_user = current_app.config.get("SMTP_USER")
    smtp_pass = current_app.config.get("SMTP_PASS")
    from_email = current_app.config.get("FROM_EMAIL") or smtp_user

    if not smtp_user or not smtp_pass or not from_email:
        return render_template(
            "interview/mail.html",
            error="SMTP not configured. Set SMTP_USER, SMTP_PASS, FROM_EMAIL.",
            meeting_date=meeting_date,
            meeting_link=meeting_link,
            to_email=to_email
        ), 500

    company_name = current_app.config.get("COMPANY_NAME", "HireNext.ai")
    support_email = current_app.config.get("SUPPORT_EMAIL", "support@hirenext.ai")

    subject, text_body, html_body = _build_interview_email_content(
        candidate_name=candidate_name,
        job_role=job_role,
        meeting_date=meeting_date,
        meeting_time=meeting_time,
        meeting_link=meeting_link,
        company_name=company_name,
        support_email=support_email,
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as e:
        return render_template(
            "interview/mail.html",
            error=f"Email send failed: {e}",
            meeting_date=meeting_date,
            meeting_link=meeting_link,
            to_email=to_email
        ), 500

    return render_template(
        "interview/mail.html",
        message="Email sent successfully ✅",
        meeting_date=meeting_date,
        meeting_link=meeting_link,
        to_email=to_email
    )


# ============================================================
# meeting.html APIs (edit interview)
# ============================================================

@interview_bp.route("/api/interview/<interview_id>", methods=["GET"])
def api_get_interview(interview_id: str):
    db = _get_db()
    oid = _oid(interview_id)
    if not oid:
        return jsonify({"ok": False, "error": "Invalid interview_id"}), 400

    row = db.interviews.find_one({"_id": oid})
    if not row:
        return jsonify({"ok": False, "error": "Interview not found"}), 404

    return jsonify({"ok": True, "interview": _json_safe(dict(row))})


@interview_bp.route("/api/interview/<interview_id>/update", methods=["POST"])
def api_update_interview(interview_id: str):
    data = request.get_json(silent=True) or {}
    patch = dict(data or {})
    patch.pop("_id", None)

    oid = _oid(interview_id)
    if not oid:
        return jsonify({"ok": False, "error": "Invalid interview_id"}), 400

    ALLOWED = {
        "title",
        "type",
        "notes",
        "date",
        "time",
        "duration",
        "start_time",
        "end_time",
        "meeting_link",
        "meeting_link_default",
        "interviewer",
        "status",
        "tz",
    }
    clean_patch = {k: v for k, v in patch.items() if k in ALLOWED}
    clean_patch["updated_at"] = datetime.now(timezone.utc)

    result = InterviewService.update_interview(
        interview_id=str(interview_id),
        patch=clean_patch
    )

    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "Update failed")}), 400

    return jsonify({
        "ok": True,
        "message": "Interview updated.",
        "interview": _json_safe(result.get("interview"))
    })


@interview_bp.route("/api/interview/<interview_id>/cancel", methods=["POST"])
def api_cancel_interview(interview_id: str):
    oid = _oid(interview_id)
    if not oid:
        return jsonify({"ok": False, "error": "Invalid interview_id"}), 400

    result = InterviewService.cancel_interview(interview_id=str(interview_id))
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "Cancel failed")}), 400

    return jsonify({
        "ok": True,
        "message": "Interview cancelled.",
        "interview": _json_safe(result.get("interview"))
    })