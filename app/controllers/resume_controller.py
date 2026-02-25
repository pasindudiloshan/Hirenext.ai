# app/controllers/resume_controller.py
# FINAL CLEAN: Multi-PDF Upload + Auto Candidate Name + PDF Preview Support

import os
import json
from uuid import uuid4
from datetime import datetime
from bson import ObjectId
from werkzeug.utils import secure_filename
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    send_from_directory
)

from app import mongo
from app.config import Config
from app.utils.pdf_utils import extract_text_from_pdf
from app.services.resume_service import ResumeScoringService
from app.utils.cv_pipeline import CVPipeline
from app.models.shortlisted_batch_model import ShortlistedBatchModel

resume_bp = Blueprint("resume_bp", __name__)
ALLOWED_EXTENSIONS = {"pdf"}


# -----------------------------------------
# Helpers
# -----------------------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Global ML Scorer (avoid reload per request)
scorer = ResumeScoringService(model_path=Config.ML_MODEL_PATH)


# -----------------------------------------
# Serve Uploaded PDFs (Preview)
# -----------------------------------------
@resume_bp.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(Config.UPLOAD_FOLDER, filename)


# -----------------------------------------
# Screening Form
# -----------------------------------------
@resume_bp.route("/", methods=["GET"])
@resume_bp.route("/new", methods=["GET"])
def screening_form():

    job_id_from_query = request.args.get("job_id")

    if job_id_from_query:
        try:
            job = mongo.db.jobs.find_one({
                "_id": ObjectId(job_id_from_query),
                "is_active": True
            })
        except Exception:
            job = None

        if job:
            current_job_id = session.get("active_job_id")

            if current_job_id != job_id_from_query:
                old_batch_id = session.get("active_batch_id")
                if old_batch_id:
                    ShortlistedBatchModel.close_batch(old_batch_id)

                inserted = ShortlistedBatchModel.create_batch(job)

                session["active_job_id"] = str(job["_id"])
                session["active_batch_id"] = str(inserted.inserted_id)

            return redirect(url_for("resume_bp.screening_form"))

    jobs = list(
        mongo.db.jobs.find({"is_active": True}).sort("created_at", -1)
    )

    active_job_id = session.get("active_job_id")
    active_batch_id = session.get("active_batch_id")

    active_job = None
    active_batch = None

    if active_job_id:
        try:
            active_job = mongo.db.jobs.find({"_id": ObjectId(active_job_id)}).limit(1)[0]
        except Exception:
            active_job = None
            session.pop("active_job_id", None)

    if active_batch_id:
        active_batch = ShortlistedBatchModel.get_batch_by_id(active_batch_id)
        if not active_batch:
            session.pop("active_batch_id", None)

    return render_template(
        "screening/upload_resume.html",
        jobs=jobs,
        active_job=active_job,
        active_job_id=active_job_id,
        active_batch=active_batch,
        active_batch_id=active_batch_id,
        screenings=[],
        screenings_json=json.dumps([])
    )


# -----------------------------------------
# Select Job
# -----------------------------------------
@resume_bp.route("/select_job", methods=["POST"])
def select_job():

    job_id = request.form.get("job_id", "").strip()

    if not job_id:
        flash("Please select a job role.", "danger")
        return redirect(url_for("resume_bp.screening_form"))

    try:
        job = mongo.db.jobs.find_one({
            "_id": ObjectId(job_id),
            "is_active": True
        })
    except Exception:
        job = None

    if not job:
        flash("Selected job not found.", "danger")
        return redirect(url_for("resume_bp.screening_form"))

    old_batch_id = session.get("active_batch_id")
    if old_batch_id:
        ShortlistedBatchModel.close_batch(old_batch_id)

    inserted = ShortlistedBatchModel.create_batch(job)

    session["active_job_id"] = str(job["_id"])
    session["active_batch_id"] = str(inserted.inserted_id)

    flash(f"New batch started for: {job.get('job_title', '')}", "success")
    return redirect(url_for("resume_bp.screening_form"))


# -----------------------------------------
# Reset Session
# -----------------------------------------
@resume_bp.route("/reset", methods=["POST"])
def reset_screening():

    batch_id = session.get("active_batch_id")

    if batch_id:
        ShortlistedBatchModel.close_batch(batch_id)

    session.pop("active_job_id", None)
    session.pop("active_batch_id", None)

    flash("Screening session reset.", "info")
    return redirect(url_for("resume_bp.screening_form"))


# -----------------------------------------
# Multi-PDF Scoring (Auto Name)
# -----------------------------------------
@resume_bp.route("/score", methods=["POST"])
def screening_score():

    job_id = (session.get("active_job_id") or "").strip()
    batch_id = (session.get("active_batch_id") or "").strip()

    if not job_id or not batch_id:
        return jsonify({
            "ok": False,
            "error": "Please select a job role first."
        }), 400

    try:
        job = mongo.db.jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        job = None

    if not job:
        return jsonify({"ok": False, "error": "Selected job not found."}), 404

    batch = ShortlistedBatchModel.get_active_batch(batch_id)
    if not batch:
        return jsonify({"ok": False, "error": "Active batch not found."}), 404

    if "resume_pdf" not in request.files:
        return jsonify({"ok": False, "error": "Please upload at least one PDF."}), 400

    files = request.files.getlist("resume_pdf")
    if not files:
        return jsonify({"ok": False, "error": "No files selected."}), 400

    upload_dir = Config.UPLOAD_FOLDER
    os.makedirs(upload_dir, exist_ok=True)

    results = []

    for file in files:

        if file.filename == "" or not allowed_file(file.filename):
            continue

        # Unique filename
        safe_name = secure_filename(file.filename)
        filename = f"{uuid4()}_{safe_name}"
        save_path = os.path.join(upload_dir, filename)
        file.save(save_path)

        resume_text = extract_text_from_pdf(save_path) or ""
        if len(resume_text.strip()) < 50:
            continue

        # ---------------- Parse CV ----------------
        parsed_row = {}
        try:
            pipeline = CVPipeline()
            df_cv = pipeline.run_single_pdf(save_path)
            parsed_row = df_cv.iloc[0].to_dict()

            for k, v in parsed_row.items():
                if isinstance(v, (list, tuple)):
                    parsed_row[k] = [str(x) for x in v]
                elif isinstance(v, dict):
                    parsed_row[k] = {str(a): str(b) for a, b in v.items()}
                else:
                    parsed_row[k] = str(v) if v is not None else ""

        except Exception as e:
            parsed_row = {"error": f"CV parsing failed: {str(e)}"}

        # ---------------- Auto Candidate Name ----------------
        auto_name = parsed_row.get("title") or "Unknown"
        auto_name = str(auto_name).strip().title()

        # ---------------- Hybrid Score ----------------
        X_df, semantic_score_0_100 = scorer.build_features_row(
            resume_text=resume_text,
            job=job,
            salary_expectation=0.0
        )

        ml_score = float(scorer.predict_ml_score(X_df))
        semantic_score = float(semantic_score_0_100) / 100.0

        final_score = round((0.65 * ml_score) + (0.35 * semantic_score), 6)
        final_score_pct = round(final_score * 100.0, 2)

        threshold = float(job.get("shortlist_threshold", 0.60))
        decision = "SHORTLIST" if final_score >= threshold else "REJECT"

        results.append({
            "_id": str(ObjectId()),
            "batch_id": batch_id,
            "candidate_name": auto_name,
            "job_id": str(job["_id"]),
            "job_title": job.get("job_title", ""),
            "pdf_filename": filename,
            "semantic_score_0_100": float(semantic_score_0_100),
            "ml_score": float(ml_score),
            "final_score": float(final_score),
            "final_score_pct": float(final_score_pct),
            "decision": decision,
            "threshold": threshold,
            "parsed_cv": parsed_row,
            "created_at": datetime.utcnow().isoformat() + "Z"
        })

    if not results:
        return jsonify({
            "ok": False,
            "error": "No valid resumes processed."
        }), 400

    return jsonify({
        "ok": True,
        "rows": results
    })


# -----------------------------------------
# Shortlist Selected
# -----------------------------------------
@resume_bp.route("/shortlist", methods=["POST"])
def shortlist_selected():

    payload = request.get_json(silent=True) or {}
    shortlisted = payload.get("shortlisted", [])

    if not isinstance(shortlisted, list) or not shortlisted:
        return jsonify({"ok": False, "error": "No candidates selected."}), 400

    batch_id = session.get("active_batch_id")
    job_id = session.get("active_job_id")

    if not batch_id or not job_id:
        return jsonify({"ok": False, "error": "No active batch found."}), 400

    batch = ShortlistedBatchModel.get_active_batch(batch_id)
    if not batch:
        return jsonify({"ok": False, "error": "Active batch not found."}), 404

    now = datetime.utcnow()
    shortlisted_docs = []

    for r in shortlisted:
        if (r.get("decision") or "").upper() != "SHORTLIST":
            continue

        shortlisted_docs.append({
            "candidate_name": r.get("candidate_name"),
            "pdf_filename": r.get("pdf_filename"),
            "final_score_pct": r.get("final_score_pct"),
            "decision": "SHORTLIST",
            "created_at": r.get("created_at"),
            "saved_at": now
        })

    if not shortlisted_docs:
        return jsonify({"ok": False, "error": "No valid shortlisted candidates."}), 400

    ShortlistedBatchModel.save_shortlisted(batch_id, shortlisted_docs)

    return jsonify({
        "ok": True,
        "saved": len(shortlisted_docs),
        "redirect": "/interview/schedule"
    })