# app/services/job_service.py

from typing import List, Tuple, Optional
from app.models.job_model import JobModel
from app.utils.skill_library import SKILL_LIBRARY


class JobService:
    """
    Service layer for Job creation & validation.
    Keeps controllers thin and centralizes business rules.
    """

    # fixed weights (same as your current controller logic)
    DEFAULT_WEIGHTS = {
        "experience": 0.50,
        "skills": 0.30,
        "summary": 0.10,
        "education": 0.10
    }

    @staticmethod
    def _to_float(value, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _split_csv_lower(raw: str) -> List[str]:
        return [s.strip().lower() for s in (raw or "").split(",") if s.strip()]

    @staticmethod
    def _split_csv_preserve(raw: str) -> List[str]:
        return [s.strip() for s in (raw or "").split(",") if s.strip()]

    @staticmethod
    def _normalize_threshold(raw_value: str, default: float = 0.60) -> float:
        """
        Accepts:
          - "0.60"  -> 0.60
          - "60"    -> 0.60 (percent safety)
          - clamps to [0.0, 1.0]
        """
        t = JobService._to_float(raw_value, default)

        # if sent as percent (e.g., 60), convert to decimal
        if t > 1:
            t = round(t / 100.0, 2)

        # clamp
        if t < 0:
            t = 0.0
        if t > 1:
            t = 1.0

        return float(f"{t:.2f}")

    @staticmethod
    def _normalize_skill_token(s: str) -> str:
        """
        Converts skill library entries like 'Machine Learning' -> 'machine learning'
        to match how we store required_skills.
        """
        return (s or "").strip().lower()

    @staticmethod
    def validate_job_inputs(
        job_title: str,
        job_description: str,
        required_skills_raw: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Basic validation for job creation.
        Returns (ok, error_message).
        """
        if not (job_title or "").strip():
            return False, "Job title is required."
        if not (job_description or "").strip():
            return False, "Job description is required."
        if not (required_skills_raw or "").strip():
            return False, "Required skills are required."
        return True, None

    @staticmethod
    def validate_skills_against_library(required_skills: List[str]) -> Tuple[List[str], List[str]]:
        """
        Optional: validate entered skills against SKILL_LIBRARY.
        Returns (valid_skills, unknown_skills).

        NOTE:
        - We do not block unknown skills by default; we just identify them.
        - You can choose to reject unknown skills in the controller if you want.
        """
        lib = {JobService._normalize_skill_token(x) for x in SKILL_LIBRARY}
        valid, unknown = [], []

        for s in required_skills:
            if s in lib:
                valid.append(s)
            else:
                unknown.append(s)

        return valid, unknown

    @staticmethod
    def create_job_from_form(form, image_path: str = "") -> Tuple[bool, str]:
        """
        Main helper for controllers:
        Takes Flask request.form (and optional image_path) and handles:
          - validation
          - parsing
          - normalization
          - persistence

        Returns: (success, message)

        image_path example:
          "uploads/jobs/my_image.png"
        """
        job_title = form.get("job_title", "").strip()
        job_description = form.get("job_description", "").strip()
        required_skills_raw = form.get("required_skills", "").strip()
        priority_keywords_raw = form.get("priority_keywords", "").strip()
        shortlist_threshold_raw = form.get("shortlist_threshold", "0.60").strip()

        ok, err = JobService.validate_job_inputs(job_title, job_description, required_skills_raw)
        if not ok:
            return False, err

        required_skills = JobService._split_csv_lower(required_skills_raw)
        priority_keywords = JobService._split_csv_preserve(priority_keywords_raw)
        shortlist_threshold = JobService._normalize_threshold(shortlist_threshold_raw, default=0.60)

        # Optional: skill library validation (non-blocking)
        _, unknown_skills = JobService.validate_skills_against_library(required_skills)

        # Store job doc with optional image_path
        job_doc = {
            "job_title": job_title,
            "job_description": job_description,
            "required_skills": required_skills,
            "priority_keywords": priority_keywords,
            "shortlist_threshold": shortlist_threshold,
            "weights": JobService.DEFAULT_WEIGHTS,

            # ✅ NEW: image for job card / view page
            "image_path": (image_path or "").strip(),

            # Optional debug field (can remove anytime)
            "unknown_skills": unknown_skills
        }

        JobModel.create(job_doc)

        # message
        if unknown_skills:
            return True, (
                "Job created ✅ (Note: some skills were not in the suggested library: "
                + ", ".join(unknown_skills) + ")"
            )

        return True, "Job created successfully ✅"