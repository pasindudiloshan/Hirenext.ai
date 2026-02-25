# app/services/resume_service.py
import re
import joblib
import pandas as pd
from typing import Dict, Any, List, Tuple

from app.services.semantic_service import SemanticMatcher  # ✅ NEW


# ----------------------------
# Helpers: basic extraction
# ----------------------------
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def _extract_years_experience(text: str) -> float:
    t = text.lower()
    patterns = [
        r"(\d+)\s*\+?\s*years?\s+of\s+experience",
        r"(\d+)\s*\+?\s*years?\s+experience",
    ]
    for p in patterns:
        m = re.search(p, t)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return 0.0

def _count_projects(text: str) -> int:
    hits = re.findall(r"\b(project|projects)\b", text.lower())
    return min(len(hits), 20)

def _detect_education(text: str) -> str:
    t = text.lower()
    if "phd" in t or "doctor of philosophy" in t:
        return "PhD"
    if "master" in t or "msc" in t or "mba" in t:
        return "Master"
    if "bachelor" in t or "bsc" in t or "degree" in t:
        return "Bachelor"
    if "diploma" in t:
        return "Diploma"
    return "Other"

def _has_certification(text: str, highlight_keywords: List[str]) -> int:
    t = text.lower()
    cert_words = ["certified", "certification", "certificate", "cpa", "acca", "cima", "pmp", "scrum"]
    if any(w in t for w in cert_words):
        return 1

    hk = " ".join(highlight_keywords or []).lower()
    if any(w in hk for w in ["cpa", "acca", "cima", "pmp"]):
        return 1
    return 0

def _skill_count(text: str, required_skills: List[str]) -> int:
    t = _normalize(text)
    req = [s.strip().lower() for s in (required_skills or []) if s.strip()]
    return sum(1 for s in req if _normalize(s) in t)


# ----------------------------
# Main scoring service
# ----------------------------
class ResumeScoringService:
    def __init__(self, model_path: str, semantic_model_name: str = "all-MiniLM-L6-v2"):
        loaded = joblib.load(model_path)

        if isinstance(loaded, dict):
            pipeline_keys = ["pipeline", "final_pipe", "full_pipeline", "model_pipeline", "preprocess_pipeline"]
            model_keys = ["model", "best_model", "clf", "estimator", "lr_model", "rf_model"]

            self.pipe = None
            for k in pipeline_keys:
                if k in loaded:
                    self.pipe = loaded[k]
                    break

            if self.pipe is None:
                for k in model_keys:
                    if k in loaded:
                        self.pipe = loaded[k]
                        break

            if self.pipe is None:
                raise ValueError(f"Bundle loaded but no pipeline/model key found. Keys: {list(loaded.keys())}")
        else:
            self.pipe = loaded

        if not (hasattr(self.pipe, "predict") or hasattr(self.pipe, "predict_proba")):
            raise TypeError(f"Loaded object is not a model/pipeline. Type={type(self.pipe)}")

        bare_names = {"LogisticRegression", "RandomForestClassifier", "KNeighborsClassifier"}
        if self.pipe.__class__.__name__ in bare_names:
            raise ValueError(
                "Your joblib contains a bare model (no preprocessing pipeline). "
                "Re-save FULL sklearn Pipeline (preprocessing + model)."
            )

        # ✅ Semantic matcher (loads once per service instance)
        self.semantic = SemanticMatcher(model_name=semantic_model_name)

    def build_features_row(
        self,
        resume_text: str,
        job: Dict[str, Any],
        salary_expectation: float = 0.0
    ) -> Tuple[pd.DataFrame, float]:
        exp_years = _extract_years_experience(resume_text)
        projects = _count_projects(resume_text)

        skill_count = _skill_count(resume_text, job.get("required_skills", []))

        # ✅ REAL semantic score (from your end-to-end notebook method)
        jd_text = job.get("job_description", "")
        semantic_score_0_100 = self.semantic.semantic_score_0_100(resume_text, jd_text)

        salary_per_exp = (salary_expectation / exp_years) if exp_years > 0 else 0.0
        project_intensity = projects / max(exp_years, 1)

        edu = _detect_education(resume_text)
        has_cert = _has_certification(resume_text, job.get("highlight_keywords", []))

        row = {
            "Experience (Years)": float(exp_years),
            "Salary Expectation ($)": float(salary_expectation),
            "Projects Count": float(projects),

            # ✅ Replace your old keyword-percentage “AI Score” with semantic score
            "AI Score (0-100)": float(semantic_score_0_100),

            "Skill_Count": float(skill_count),
            "Salary_Per_Experience": float(salary_per_exp),
            "Project_Intensity": float(project_intensity),
            "Education": edu,
            "Job Role": job.get("job_title", "Other"),
            "Has_Certification": int(has_cert),
        }

        return pd.DataFrame([row]), float(semantic_score_0_100)

    def predict_ml_score(self, X_df: pd.DataFrame) -> float:
        if hasattr(self.pipe, "predict_proba"):
            proba = self.pipe.predict_proba(X_df)[0, 1]
            return float(round(proba, 4))

        pred = self.pipe.predict(X_df)[0]
        try:
            return float(pred)
        except Exception:
            return 0.0