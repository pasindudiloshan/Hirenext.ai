# app/services/cv_scorer.py
import re
import ast
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, util


class CVScorer:
    def __init__(
        self,
        job_title: str,
        job_description: str,
        required_skills: list,
        highlight_keywords: list,
        weights: dict,
        model_name: str = "all-MiniLM-L6-v2",
        title_sim_threshold: float = 0.6,
        shared_model: SentenceTransformer | None = None,
    ):
        self.job_title = job_title or ""
        self.job_description = job_description or ""
        self.required_skills = required_skills or []
        self.highlight_keywords = highlight_keywords or []
        self.weights = weights or {"experience": 0.5, "skills": 0.3, "summary": 0.1, "education": 0.1}
        self.title_sim_threshold = title_sim_threshold

        # ✅ reuse model (important in Flask)
        self.model = shared_model if shared_model is not None else SentenceTransformer(model_name)

        # Pre-encode targets
        self.job_title_emb = self.model.encode(self.job_title, convert_to_tensor=True)
        self.job_desc_emb = self.model.encode(self.job_description, convert_to_tensor=True)

    # -------- Title gate (optional in single-CV mode) --------
    def title_pass(self, title: str) -> bool:
        if not title or pd.isna(title):
            return False

        t_cv = str(title).lower().strip()
        t_job = self.job_title.lower().strip()

        if t_job in t_cv or t_cv in t_job:
            return True

        emb_cv = self.model.encode(t_cv, convert_to_tensor=True)
        sim = util.pytorch_cos_sim(emb_cv, self.job_title_emb).item()
        return sim >= self.title_sim_threshold

    # ---------------- Skills ----------------
    def score_skills(self, cv_skills_raw) -> float:
        if not self.required_skills:
            return 0.0
        try:
            cv_skills = ast.literal_eval(cv_skills_raw) if isinstance(cv_skills_raw, str) else cv_skills_raw
        except Exception:
            cv_skills = []

        if not cv_skills:
            return 0.0

        cv_low = [str(s).lower().strip() for s in cv_skills]
        req_low = [s.lower().strip() for s in self.required_skills]
        n = len(req_low)

        hard = []
        remain = []
        for s in req_low:
            (hard if s in cv_low else remain).append(s)

        score = len(hard)

        if remain:
            emb_cv = self.model.encode(cv_low, convert_to_tensor=True)
            cv_used = set()

            for s in remain:
                emb_s = self.model.encode(s, convert_to_tensor=True)
                sims = util.pytorch_cos_sim(emb_s, emb_cv)[0]

                for idx in cv_used:
                    sims[idx] = -1

                best_idx = torch.argmax(sims).item()
                best_sim = sims[best_idx].item()

                if best_sim > 0:
                    score += best_sim
                    cv_used.add(best_idx)

        return round(score / n, 4)

    # ---------------- Summary ----------------
    def score_summary_raw(self, summary) -> float:
        if not summary or pd.isna(summary):
            return 0.0

        def clean(text):
            fluff = ["professional", "dedicated", "hardworking", "seeking", "opportunity", "proven", "years", "experience"]
            text = str(text).lower()
            for w in fluff:
                text = re.sub(rf"\b{w}\b", "", text)
            return re.sub(r"\s+", " ", text).strip()

        chunks = [c.strip() for c in str(summary).replace("\n", ".").split(".") if len(c.strip()) > 10]
        if not chunks:
            return 0.0

        emb_chunks = self.model.encode([clean(c) for c in chunks], convert_to_tensor=True)
        sims = util.pytorch_cos_sim(emb_chunks, self.job_desc_emb).flatten().tolist()
        score = max(sims) if sims else 0.0

        bonus = sum(0.5 for kw in self.highlight_keywords if kw.lower() in str(summary).lower())
        return float(score + bonus)

    # ---------------- Education ----------------
    def score_education_raw(self, edu) -> float:
        if not edu or pd.isna(edu):
            return 0.0

        try:
            cert = int(re.search(r"cert_count:\s*(\d+)", edu).group(1))
            content = re.search(r"content:\s*(.*?)\]\]", edu).group(1)
        except Exception:
            return 0.0

        degree_weights = {
            "phd": 2.0, "doctorate": 2.0,
            "master": 1.5, "msc": 1.5, "mba": 1.5,
            "bachelor": 1.2, "ba": 1.2, "bs": 1.2,
            "diploma": 1.0,
            "high school": 0.5,
        }

        weight = 0.5
        content_low = str(content).lower()
        for d, w in degree_weights.items():
            if d in content_low:
                weight = max(weight, w)

        emb = self.model.encode(content, convert_to_tensor=True)
        sim = max(0.0, util.pytorch_cos_sim(emb, self.job_desc_emb).item())

        return float((sim * weight) + (cert * 0.1))

    # ---------------- Experience ----------------
    def score_experience_raw(self, exp) -> float:
        if not exp or pd.isna(exp):
            return 0.0

        blocks = re.findall(r"\[\[(.*?)\]\]", exp, re.DOTALL)
        if not blocks:
            return 0.0

        total = 0.0

        for blk in blocks:
            parts = blk.split("][")
            if len(parts) < 3:
                continue

            role = parts[0].replace("role:", "").strip()
            years = float(re.findall(r"[\d.]+", parts[1])[0]) if re.findall(r"[\d.]+", parts[1]) else 1.0
            content = parts[2].replace("content:", "").strip()

            duration = np.log1p(years) + 1.0

            role_sim = util.pytorch_cos_sim(
                self.model.encode(role, convert_to_tensor=True),
                self.job_title_emb
            ).item()

            chunks = [c for c in content.split(".") if len(c.strip()) > 15]
            content_score = 0.0
            if chunks:
                embs = self.model.encode(chunks, convert_to_tensor=True)
                sims = sorted(util.pytorch_cos_sim(embs, self.job_desc_emb).flatten().tolist(), reverse=True)
                content_score = max(0.0, sims[0]) + sum(s * 0.2 for s in sims[1:] if s > 0.5)

            kw_bonus = sum(0.2 for kw in self.highlight_keywords if kw.lower() in content.lower())
            relevance = (max(0.0, role_sim) * 5.0) + (content_score * 3.0) + kw_bonus

            total += relevance * duration

        return float(round(total, 4))

    # ---------------- Single CV scoring ----------------
    def score_one(self, df_one: pd.DataFrame) -> dict:
        """
        df_one is a single-row DataFrame produced by CVPipeline.run_single_pdf()
        returns dict with component scores + total_score
        """
        if df_one.empty:
            return {"total_score": 0.0, "passed_title_gate": False}

        row = df_one.iloc[0]
        passed = self.title_pass(row.get("title", ""))

        # If you want strict gate, keep it.
        # If you want to still score even if title fails, set passed=True here.
        if not passed:
            return {"total_score": 0.0, "passed_title_gate": False}

        score_skills = self.score_skills(row.get("skills_list", []))
        summary_raw = self.score_summary_raw(row.get("summary", ""))
        edu_raw = self.score_education_raw(row.get("education_enriched", ""))
        exp_raw = self.score_experience_raw(row.get("experience_enriched", ""))

        # Single CV: normalization isn't meaningful (min=max). We'll map raw -> bounded values.
        # Simple safe normalization:
        score_summary_final = max(0.0, min(1.0, float(summary_raw)))
        score_education_final = max(0.0, min(1.0, float(edu_raw)))
        # exp_raw can be >1, compress with log
        score_experience_final = max(0.0, min(1.0, float(np.tanh(exp_raw / 5.0))))

        total_score = (
            score_experience_final * self.weights.get("experience", 0.5) +
            score_skills * self.weights.get("skills", 0.3) +
            score_summary_final * self.weights.get("summary", 0.1) +
            score_education_final * self.weights.get("education", 0.1)
        )

        return {
            "passed_title_gate": True,
            "score_skills": round(float(score_skills), 4),
            "score_summary_final": round(float(score_summary_final), 4),
            "score_education_final": round(float(score_education_final), 4),
            "score_experience_final": round(float(score_experience_final), 4),
            "total_score": round(float(total_score), 4),
        }