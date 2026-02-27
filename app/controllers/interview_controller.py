from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import smtplib
from email.message import EmailMessage

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, render_template, request

from app.models.shortlisted_batch_model import ShortlistedBatchModel
from app.services.interview_service import InterviewService

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
    batch_id = (request.args.get("batch_id") or "").strip()  # optional

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

    # Right side: upcoming interviews for batch
    recent_interviews: List[Dict[str, Any]] = []
    total_scheduled_for_active_batch = 0

    try:
        if active_batch and active_batch.get("_id"):
            bid = str(active_batch["_id"])

            # total interviews scheduled for this batch (all dates)
            total_scheduled_for_active_batch = int(
                db.interviews.count_documents({"batch_id": bid}) or 0
            )

            # recent upcoming (for right pane)
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

    # Add counts per batch for left rail
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
        time_slots=[],  # JS renders slots
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

    # remaining-to-schedule (server computed)
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

    # ✅ Important: service will also block when remaining_to_schedule == 0
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
    """
    Existing endpoint: currently just marks invites as sent in DB.
    (You can keep it, and use manual popup for actual sending.)
    """
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
    """
    Sends an email to a candidate using Gmail SMTP (App Password).
    Form POST from mail.html.
    """
    to_email = (request.form.get("to_email") or "").strip()
    meeting_link = (request.form.get("meeting_link") or "").strip()
    meeting_date = (request.form.get("meeting_date") or "").strip()

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

    subject = "Interview Shortlisted - Meeting Details"
    body = (
        "Hi,\n\n"
        "You have been shortlisted for an interview.\n\n"
        f"Meeting Date: {meeting_date}\n"
        f"Meeting Link: {meeting_link}\n\n"
        "Thanks,\nHireNext.ai"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

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

    return jsonify({"ok": True, "message": "Interview updated.", "interview": _json_safe(result.get("interview"))})


@interview_bp.route("/api/interview/<interview_id>/cancel", methods=["POST"])
def api_cancel_interview(interview_id: str):
    oid = _oid(interview_id)
    if not oid:
        return jsonify({"ok": False, "error": "Invalid interview_id"}), 400

    result = InterviewService.cancel_interview(interview_id=str(interview_id))
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "Cancel failed")}), 400

    return jsonify({"ok": True, "message": "Interview cancelled.", "interview": _json_safe(result.get("interview"))})