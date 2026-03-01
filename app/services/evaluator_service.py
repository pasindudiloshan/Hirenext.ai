# app/services/evaluator_service.py  ✅ UPDATED (Option A) — aligned with your JSON + safe + fast
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class _EmbedConfig:
    # Default SBERT model name (downloads if not found locally)
    model_name: str = "all-MiniLM-L6-v2"
    # If you already have a local SentenceTransformer folder, set:
    #   SBERT_MODEL_PATH=app/data/ml_models/embedder_all_MiniLM_L6_v2
    env_model_path_key: str = "SBERT_MODEL_PATH"


class EvaluatorService:
    """
    Option A evaluator: Rubric scoring + Concept correctness.

    ✅ What it does:
      - Loads SBERT (SentenceTransformer) once (cached)
      - Embeds answer + rubric points + concept synonyms
      - Rubric score out of 10
      - Optional correctness checks:
          - required concepts hit count
          - red flag keyword triggers
          - uses threshold from your JSON: correctness.bert_threshold
      - Returns breakdown fields for Results page:
          awarded_points, missed_points, rubric_details,
          concept_details, red_flags_triggered, feedback

    ✅ JSON keys supported (your bank):
      question["rubric"] -> [{point, score}]
      question["correctness"] -> {
          enabled: bool,
          required_concepts: [{concept, synonyms}],
          min_concepts: int,
          bert_threshold: float,
          red_flags: [str]
      }

    Optional overrides (if you ever add them):
      question["rubric_similarity_threshold"]
      question["rubric_soft_scoring"]
      question["rubric_similarity_cap"]
      question["concept_similarity_threshold"]  (fallback if bert_threshold absent)
    """

    _embedder = None
    _cfg = _EmbedConfig()

    _text_vec_cache: Dict[str, np.ndarray] = {}
    _text_vec_cache_max = 4000

    # -------------------------
    # Model loader
    # -------------------------
    @staticmethod
    def _ensure_model():
        if EvaluatorService._embedder is not None:
            return EvaluatorService._embedder

        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise RuntimeError(
                "sentence-transformers is required. Install: pip install sentence-transformers"
            ) from e

        local_path = os.getenv(EvaluatorService._cfg.env_model_path_key, "").strip()
        if local_path and os.path.exists(local_path):
            EvaluatorService._embedder = SentenceTransformer(local_path)
        else:
            EvaluatorService._embedder = SentenceTransformer(EvaluatorService._cfg.model_name)

        return EvaluatorService._embedder

    # -------------------------
    # Embedding helper (cached)
    # -------------------------
    @staticmethod
    def _embed(text: str) -> np.ndarray:
        """
        Returns normalized embedding vector for text (shape: [dim]).
        Uses an in-memory cache for speed.
        """
        key = (text or "").strip()
        model = EvaluatorService._ensure_model()

        if not key:
            dim = model.get_sentence_embedding_dimension()
            return np.zeros((dim,), dtype=np.float32)

        cached = EvaluatorService._text_vec_cache.get(key)
        if cached is not None:
            return cached

        vec = model.encode([key], normalize_embeddings=True)[0].astype(np.float32)

        if len(EvaluatorService._text_vec_cache) >= EvaluatorService._text_vec_cache_max:
            EvaluatorService._text_vec_cache.clear()
        EvaluatorService._text_vec_cache[key] = vec
        return vec

    # -------------------------
    # Similarity helper
    # -------------------------
    @staticmethod
    def _cos_sim(a: np.ndarray, b: np.ndarray) -> float:
        """
        Cosine similarity for normalized vectors == dot product.
        """
        if a is None or b is None:
            return 0.0
        if not np.any(a) or not np.any(b):
            return 0.0
        return float(np.dot(a, b))

    # -------------------------
    # Concept hit check
    # -------------------------
    @staticmethod
    def _concept_hit(
        answer_text: str,
        answer_vec: np.ndarray,
        concept: Dict[str, Any],
        concept_sim_threshold: float,
    ) -> Tuple[bool, str, float, str]:
        """
        Returns (hit, matched_by, best_sim, matched_term)
          matched_by: "keyword" | "semantic" | ""
        """
        synonyms = concept.get("synonyms", []) or []
        concept_name = (concept.get("concept") or "").strip()
        lower = (answer_text or "").lower()

        # 1) Keyword check
        for s in synonyms:
            s = (s or "").strip()
            if s and s.lower() in lower:
                return True, "keyword", 1.0, s

        # 2) Semantic check
        candidates = [concept_name] + [str(s).strip() for s in synonyms]
        best_sim = 0.0
        best_term = ""

        for cand in candidates:
            cand = (cand or "").strip()
            if not cand:
                continue
            cand_vec = EvaluatorService._embed(cand)
            sim = EvaluatorService._cos_sim(answer_vec, cand_vec)
            if sim > best_sim:
                best_sim = sim
                best_term = cand

        if best_sim >= concept_sim_threshold:
            return True, "semantic", float(best_sim), best_term

        return False, "", float(best_sim), best_term

    # -------------------------
    # Main evaluation
    # -------------------------
    @staticmethod
    def evaluate_answer(
        question: Dict[str, Any],
        answer_text: str,
        *,
        precomputed_rubric_vectors: Optional[List[np.ndarray]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate one answer for one question.
        Returns dict with rubric_score (0-10), concept_correct, feedback + breakdown fields.
        """
        answer_text = (answer_text or "").strip()

        correctness_cfg = question.get("correctness", {}) or {}
        concept_enabled = bool(correctness_cfg.get("enabled", False))

        if not answer_text:
            return {
                "rubric_score": 0.0,
                "concept_correct": False if concept_enabled else True,
                "awarded_points": [],
                "missed_points": [],
                "rubric_details": [],
                "concept_details": {"enabled": concept_enabled, "hits": [], "misses": []},
                "red_flags_triggered": [],
                "feedback": "No answer detected.",
            }

        # ---------- thresholds ----------
        # Rubric threshold: allow per-question override else default
        rubric_threshold = float(question.get("rubric_similarity_threshold", 0.55))
        rubric_soft_scoring = bool(question.get("rubric_soft_scoring", False))
        rubric_cap = float(question.get("rubric_similarity_cap", 0.80))

        # Concept threshold: prefer your JSON correctness.bert_threshold first
        # else allow question concept_similarity_threshold else default 0.60
        concept_sim_threshold = float(
            correctness_cfg.get("bert_threshold", question.get("concept_similarity_threshold", 0.60))
        )

        rubric = question.get("rubric", []) or []
        answer_vec = EvaluatorService._embed(answer_text)

        # -------------------------
        # Rubric scoring
        # -------------------------
        rubric_points_total = 0.0
        rubric_points_awarded = 0.0

        awarded_points: List[str] = []
        missed_points: List[str] = []
        rubric_details: List[Dict[str, Any]] = []

        use_precomputed = (
            precomputed_rubric_vectors is not None
            and isinstance(precomputed_rubric_vectors, list)
            and len(precomputed_rubric_vectors) == len(rubric)
        )

        for idx, item in enumerate(rubric):
            point_text = str(item.get("point") or "").strip()
            weight = float(item.get("score") or 0.0)

            if not point_text or weight <= 0:
                continue

            rubric_points_total += weight

            point_vec = precomputed_rubric_vectors[idx] if use_precomputed else EvaluatorService._embed(point_text)
            sim = EvaluatorService._cos_sim(answer_vec, point_vec)

            if rubric_soft_scoring:
                # partial credit based on similarity
                floor = rubric_threshold * 0.85
                cap = max(rubric_cap, rubric_threshold + 1e-6)

                if sim >= floor:
                    scaled = (sim - rubric_threshold) / (cap - rubric_threshold)
                    scaled = float(max(0.0, min(1.0, scaled)))
                    gained = weight * scaled
                    rubric_points_awarded += gained

                    if scaled >= 0.5:
                        awarded_points.append(point_text)
                    else:
                        missed_points.append(point_text)

                    rubric_details.append({
                        "point": point_text,
                        "weight": weight,
                        "similarity": round(sim, 4),
                        "awarded": round(gained, 3),
                        "mode": "soft",
                    })
                else:
                    missed_points.append(point_text)
                    rubric_details.append({
                        "point": point_text,
                        "weight": weight,
                        "similarity": round(sim, 4),
                        "awarded": 0.0,
                        "mode": "soft",
                    })
            else:
                # threshold scoring
                if sim >= rubric_threshold:
                    rubric_points_awarded += weight
                    awarded_points.append(point_text)
                    rubric_details.append({
                        "point": point_text,
                        "weight": weight,
                        "similarity": round(sim, 4),
                        "awarded": weight,
                        "mode": "threshold",
                    })
                else:
                    missed_points.append(point_text)
                    rubric_details.append({
                        "point": point_text,
                        "weight": weight,
                        "similarity": round(sim, 4),
                        "awarded": 0.0,
                        "mode": "threshold",
                    })

        # Normalize rubric to /10
        if rubric_points_total <= 0:
            rubric_score_10 = 0.0
        else:
            rubric_score_10 = (rubric_points_awarded / rubric_points_total) * 10.0
            rubric_score_10 = float(max(0.0, min(10.0, round(rubric_score_10, 2))))

        # -------------------------
        # Concept correctness
        # -------------------------
        concept_correct = True
        red_flags_triggered: List[str] = []
        concept_details: Dict[str, Any] = {"enabled": concept_enabled, "hits": [], "misses": []}

        if concept_enabled:
            required = correctness_cfg.get("required_concepts", []) or []
            min_required = int(correctness_cfg.get("min_concepts", 1))
            red_flags = correctness_cfg.get("red_flags", []) or []

            lower = answer_text.lower()

            # Red flags are keyword-based (fast + predictable)
            for flag in red_flags:
                flag = (flag or "").strip()
                if flag and flag.lower() in lower:
                    red_flags_triggered.append(flag)

            hits = 0
            for c in required:
                hit, matched_by, best_sim, matched_term = EvaluatorService._concept_hit(
                    answer_text=answer_text,
                    answer_vec=answer_vec,
                    concept=c,
                    concept_sim_threshold=concept_sim_threshold,
                )
                concept_name = (c.get("concept") or "").strip() or "concept"

                if hit:
                    hits += 1
                    concept_details["hits"].append({
                        "concept": concept_name,
                        "matched_by": matched_by,
                        "similarity": round(best_sim, 4),
                        "matched_term": matched_term,
                    })
                else:
                    concept_details["misses"].append({
                        "concept": concept_name,
                        "best_similarity": round(best_sim, 4),
                        "closest_term": matched_term,
                    })

            if red_flags_triggered:
                concept_correct = False
            elif hits < min_required:
                concept_correct = False

        # -------------------------
        # Feedback generation (simple)
        # -------------------------
        if rubric_score_10 >= 8:
            feedback = "Strong answer. Well explained."
        elif rubric_score_10 >= 5:
            feedback = "Decent answer. Could include more depth."
        else:
            feedback = "Weak explanation. Key concepts missing."

        if missed_points:
            feedback += " Consider mentioning: " + ", ".join(missed_points[:2])

        if concept_enabled and not concept_correct:
            if red_flags_triggered:
                feedback += " Also avoid incorrect statements flagged in your answer."
            elif concept_details.get("misses"):
                feedback += " Try to cover the required concepts more clearly."

        return {
            "rubric_score": rubric_score_10,
            "concept_correct": concept_correct,
            "awarded_points": awarded_points,
            "missed_points": missed_points,
            "rubric_details": rubric_details,
            "concept_details": concept_details,
            "red_flags_triggered": red_flags_triggered,
            "feedback": feedback,
        }