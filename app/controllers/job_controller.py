import os
from werkzeug.utils import secure_filename
from flask import (
    Blueprint,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app
)

from app.utils.skill_library import ALL_SKILLS
from app.models.job_model import JobModel
from app.services.job_service import JobService


# -----------------------------
# Blueprint
# -----------------------------
job_bp = Blueprint("job_bp", __name__)


# -----------------------------
# Image Configuration
# -----------------------------
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -----------------------------
# Helper: Serialize Mongo ObjectId
# -----------------------------
def serialize_job(job: dict) -> dict:
    """Convert Mongo _id to string for JSON responses."""
    if not job:
        return job
    job = dict(job)
    job["_id"] = str(job.get("_id"))
    return job


# =====================================================
# 🟦 DASHBOARD (MOVED TO /dashboard)
# =====================================================
@job_bp.route("/dashboard", methods=["GET"])
def dashboard_page():
    jobs = JobModel.get_all()
    return render_template("dashboard.html", jobs=jobs)


# =====================================================
# 🟦 JOB LIST PAGE
# =====================================================
@job_bp.route("/jobs", methods=["GET"])
def list_jobs_page():
    jobs = JobModel.get_all()
    return render_template("jobs/list_jobs.html", jobs=jobs)


# =====================================================
# 🟦 CREATE JOB (FORM)
# =====================================================
@job_bp.route("/jobs/new", methods=["GET"])
def create_job_form():
    """
    Render create job form.
    IMPORTANT: Pass ALL_SKILLS (flattened list)
    """
    return render_template(
        "jobs/create_job.html",
        skill_library=ALL_SKILLS
    )


# =====================================================
# 🟦 CREATE JOB (SUBMIT) + IMAGE UPLOAD
# =====================================================
@job_bp.route("/jobs/new", methods=["POST"])
def create_job_submit():
    """
    Handle job creation form submission with optional image upload.
    """
    image_path = ""

    # 1️⃣ Handle image upload
    file = request.files.get("job_image")

    if file and file.filename:
        if not allowed_file(file.filename):
            flash("Invalid image type. Allowed: png, jpg, jpeg, webp", "danger")
            return render_template(
                "jobs/create_job.html",
                skill_library=ALL_SKILLS
            )

        filename = secure_filename(file.filename)

        # Folder: app/static/uploads/jobs/
        upload_folder = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
            "jobs"
        )

        # Create folder if not exists
        os.makedirs(upload_folder, exist_ok=True)

        save_path = os.path.join(upload_folder, filename)

        # Prevent overwrite (auto rename if exists)
        if os.path.exists(save_path):
            name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(upload_folder, f"{name}_{counter}{ext}")):
                counter += 1
            filename = f"{name}_{counter}{ext}"
            save_path = os.path.join(upload_folder, filename)

        file.save(save_path)

        # Path to store in MongoDB
        image_path = f"uploads/jobs/{filename}"

    # 2️⃣ Create job using service (pass image_path)
    success, message = JobService.create_job_from_form(
        request.form,
        image_path=image_path
    )

    if not success:
        flash(message, "danger")
        return render_template(
            "jobs/create_job.html",
            skill_library=ALL_SKILLS
        )

    flash(message, "success")
    return redirect(url_for("job_bp.list_jobs_page"))


# =====================================================
# 🟦 VIEW SINGLE JOB
# =====================================================
@job_bp.route("/jobs/<job_id>", methods=["GET"])
def view_job(job_id):
    job = JobModel.get_by_id(job_id)

    if not job:
        return "Job not found", 404

    return render_template("jobs/view_job.html", job=job)


# =====================================================
# 🟦 OPTIONAL: JSON API
# =====================================================
@job_bp.route("/api/jobs", methods=["GET"])
def list_jobs_api():
    jobs = JobModel.get_all()
    return jsonify([serialize_job(j) for j in jobs]), 200