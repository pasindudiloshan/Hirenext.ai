# app/controllers/interview_controller.py

from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, flash

from app import mongo

interview_bp = Blueprint("interview_bp", __name__)


@interview_bp.route("/schedule", methods=["GET"])
def schedule_form():
    jobs = list(mongo.db.jobs.find({"is_active": True}).sort("created_at", -1))

    shortlisted = list(
        mongo.db.screenings.find({"decision": "SHORTLIST"}).sort("created_at", -1)
    )

    for s in shortlisted:
        s["_id"] = str(s["_id"])

    return render_template("interview/schedule.html", jobs=jobs, shortlisted=shortlisted)


@interview_bp.route("/schedule", methods=["POST"])
def create_schedule():
    screening_ids = request.form.getlist("screening_ids")
    interview_date = request.form.get("interview_date")
    interview_time = request.form.get("interview_time")
    location = request.form.get("location", "").strip()
    interviewer = request.form.get("interviewer", "").strip()
    notes = request.form.get("notes", "").strip()

    if not screening_ids:
        flash("Please select at least one candidate.", "warning")
        return redirect("/interview/schedule")

    if not interview_date or not interview_time:
        flash("Interview date and time are required.", "danger")
        return redirect("/interview/schedule")

    interview_at = f"{interview_date} {interview_time}"

    obj_ids = []
    for sid in screening_ids:
        try:
            obj_ids.append(ObjectId(sid))
        except Exception:
            pass

    selected = list(mongo.db.screenings.find({"_id": {"$in": obj_ids}}))

    created = 0
    for s in selected:
        mongo.db.interviews.insert_one({
            "screening_id": str(s["_id"]),
            "candidate_name": s.get("candidate_name", "Unknown"),
            "job_id": s.get("job_id"),
            "job_title": s.get("job_title", ""),
            "final_score_pct": s.get("final_score_pct", 0),

            "interview_at": interview_at,
            "location": location,
            "interviewer": interviewer,
            "notes": notes,

            "status": "SCHEDULED",
            "created_at": datetime.utcnow()
        })
        created += 1

    flash(f"✅ Interview scheduled for {created} candidate(s).", "success")
    return redirect("/interview/schedule")