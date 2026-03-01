# app/services/interview_ai_model_service.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    import joblib  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("joblib is required. Install: pip install joblib") from e


@dataclass
class ModelPaths:
    """
    Default layout (your current project):
      app/data/ml_models/
        answer_quality_rf_TUNED.joblib
        interview_model.joblib
        label_encoder.joblib
        score_map.json
        sbert_config.json
        embedder_all_MiniLM_L6_v2/
    """
    base_dir: str

    @property
    def rf_quality_path(self) -> str:
        return os.path.join(self.base_dir, "answer_quality_rf_TUNED.joblib")

    @property
    def interview_model_path(self) -> str:
        return os.path.join(self.base_dir, "interview_model.joblib")

    @property
    def label_encoder_path(self) -> str:
        return os.path.join(self.base_dir, "label_encoder.joblib")

    @property
    def score_map_path(self) -> str:
        return os.path.join(self.base_dir, "score_map.json")

    @property
    def sbert_config_path(self) -> str:
        return os.path.join(self.base_dir, "sbert_config.json")

    @property
    def embedder_folder_path(self) -> str:
        return os.path.join(self.base_dir, "embedder_all_MiniLM_L6_v2")


class InterviewAIModelService:
    """
    Option B scorer (ML models) — Hybrid companion for Option A.

    What it does:
      - Generates an embedding for the transcript (SentenceTransformer)
      - Runs ML model(s) to get:
          label (via label encoder)
          quality (optional)
          score_0_10 (from score_map or probability-based fallback)

    Returns dict like:
      {
        "label": "GOOD",
        "quality": "HIGH",
        "score_0_10": 7.8
      }

    Environment overrides:
      ML_MODELS_DIR=app/data/ml_models
      SBERT_MODEL_PATH=app/data/ml_models/embedder_all_MiniLM_L6_v2
    """

    # ---- singletons ----
    _loaded: bool = False
    _paths: Optional[ModelPaths] = None

    _embedder = None
    _interview_model = None
    _rf_quality_model = None
    _label_encoder = None
    _score_map: Dict[str, Any] = {}

    # ---- tiny cache for embeddings ----
    _vec_cache: Dict[str, np.ndarray] = {}
    _vec_cache_max: int = 2000

    # -------------------------
    # Public API
    # -------------------------
    @staticmethod
    def score_answer(transcript: str) -> Dict[str, Any]:
        """
        Main entry point used by interview_ai_controller.py
        """
        transcript = (transcript or "").strip()
        if not transcript:
            return {"label": None, "quality": None, "score_0_10": 0.0}

        try:
            InterviewAIModelService._ensure_loaded()
        except Exception as e:
            # Non-fatal; controller will still work with Option A only
            return {"label": None, "quality": None, "score_0_10": None, "error": str(e)}

        vec = InterviewAIModelService._embed(transcript)

        label, label_proba = InterviewAIModelService._predict_label(vec)
        quality = InterviewAIModelService._predict_quality(vec)

        score_0_10 = InterviewAIModelService._score_from_label_or_proba(label, label_proba)

        return {
            "label": label,
            "quality": quality,
            "score_0_10": score_0_10,
        }

    # -------------------------
    # Loaders
    # -------------------------
    @staticmethod
    def _ensure_loaded() -> None:
        if InterviewAIModelService._loaded:
            return

        base_dir = os.getenv("ML_MODELS_DIR", "").strip()
        if not base_dir:
            # default for your repo
            base_dir = os.path.join("app", "data", "ml_models")

        InterviewAIModelService._paths = ModelPaths(base_dir=base_dir)

        # Load score_map.json (optional)
        InterviewAIModelService._score_map = {}
        if os.path.exists(InterviewAIModelService._paths.score_map_path):
            with open(InterviewAIModelService._paths.score_map_path, "r", encoding="utf-8") as f:
                InterviewAIModelService._score_map = json.load(f) or {}

        # Load label encoder (optional but recommended)
        if os.path.exists(InterviewAIModelService._paths.label_encoder_path):
            InterviewAIModelService._label_encoder = joblib.load(InterviewAIModelService._paths.label_encoder_path)

        # Load interview_model.joblib (recommended)
        if os.path.exists(InterviewAIModelService._paths.interview_model_path):
            InterviewAIModelService._interview_model = joblib.load(InterviewAIModelService._paths.interview_model_path)

        # Load answer_quality_rf_TUNED.joblib (optional)
        if os.path.exists(InterviewAIModelService._paths.rf_quality_path):
            InterviewAIModelService._rf_quality_model = joblib.load(InterviewAIModelService._paths.rf_quality_path)

        # Ensure at least one model exists
        if InterviewAIModelService._interview_model is None and InterviewAIModelService._rf_quality_model is None:
            raise FileNotFoundError(
                f"No Option B models found in: {base_dir}. "
                f"Expected interview_model.joblib and/or answer_quality_rf_TUNED.joblib"
            )

        # Load embedder
        InterviewAIModelService._embedder = InterviewAIModelService._load_embedder()

        InterviewAIModelService._loaded = True

    @staticmethod
    def _load_embedder():
        """
        Priority:
          1) env SBERT_MODEL_PATH if exists
          2) sbert_config.json if it points to a local folder/name
          3) default local folder: embedder_all_MiniLM_L6_v2/
          4) fallback to downloading "all-MiniLM-L6-v2" (needs internet)
        """
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise RuntimeError(
                "sentence-transformers is required for Option B. Install: pip install sentence-transformers"
            ) from e

        paths = InterviewAIModelService._paths
        assert paths is not None

        env_path = os.getenv("SBERT_MODEL_PATH", "").strip()
        if env_path and os.path.exists(env_path):
            return SentenceTransformer(env_path)

        # Try sbert_config.json
        if os.path.exists(paths.sbert_config_path):
            try:
                with open(paths.sbert_config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f) or {}
                # common keys people store
                candidate = (
                    cfg.get("model_path")
                    or cfg.get("local_path")
                    or cfg.get("path")
                    or cfg.get("model_name")
                    or cfg.get("name")
                )
                if candidate:
                    candidate = str(candidate).strip()
                    if os.path.exists(candidate):
                        return SentenceTransformer(candidate)
                    # If it's a HF name, SentenceTransformer will try downloading it
                    return SentenceTransformer(candidate)
            except Exception:
                pass

        # Default local folder in your repo
        if os.path.exists(paths.embedder_folder_path):
            return SentenceTransformer(paths.embedder_folder_path)

        # Last resort: download (may fail if server has no internet)
        return SentenceTransformer("all-MiniLM-L6-v2")

    # -------------------------
    # Embeddings
    # -------------------------
    @staticmethod
    def _embed(text: str) -> np.ndarray:
        text = (text or "").strip()
        if not text:
            return np.zeros((384,), dtype=np.float32)

        cached = InterviewAIModelService._vec_cache.get(text)
        if cached is not None:
            return cached

        emb = InterviewAIModelService._embedder.encode([text], normalize_embeddings=True)[0]
        vec = np.asarray(emb, dtype=np.float32)

        # bounded cache
        if len(InterviewAIModelService._vec_cache) >= InterviewAIModelService._vec_cache_max:
            InterviewAIModelService._vec_cache.clear()
        InterviewAIModelService._vec_cache[text] = vec
        return vec

    # -------------------------
    # Predictions
    # -------------------------
    @staticmethod
    def _predict_label(vec: np.ndarray) -> Tuple[Optional[str], Optional[float]]:
        """
        Predict label using interview_model if available.
        Returns (label, probability_of_label) if possible.
        """
        model = InterviewAIModelService._interview_model
        le = InterviewAIModelService._label_encoder

        if model is None:
            return None, None

        X = vec.reshape(1, -1)

        label: Optional[str] = None
        proba: Optional[float] = None

        # Prefer predict_proba when available
        if hasattr(model, "predict_proba"):
            try:
                probs = model.predict_proba(X)[0]
                idx = int(np.argmax(probs))
                proba = float(probs[idx])

                pred = idx
                # decode via label encoder if exists
                if le is not None and hasattr(le, "inverse_transform"):
                    label = str(le.inverse_transform([pred])[0])
                else:
                    # if model.classes_ are strings
                    if hasattr(model, "classes_"):
                        label = str(model.classes_[idx])
                    else:
                        label = str(pred)
                return label, proba
            except Exception:
                pass

        # Fallback: predict()
        try:
            pred = model.predict(X)[0]
            if le is not None and hasattr(le, "inverse_transform"):
                label = str(le.inverse_transform([pred])[0])
            else:
                label = str(pred)
            return label, None
        except Exception:
            return None, None

    @staticmethod
    def _predict_quality(vec: np.ndarray) -> Optional[str]:
        """
        Predict quality bucket using RF quality model if present.
        If the RF model predicts numeric classes, we return the raw class as string.
        """
        model = InterviewAIModelService._rf_quality_model
        if model is None:
            return None

        X = vec.reshape(1, -1)

        # Try predict()
        try:
            pred = model.predict(X)[0]
            # If model has classes and pred is index, keep as string
            return str(pred)
        except Exception:
            return None

    # -------------------------
    # Scoring
    # -------------------------
    @staticmethod
    def _score_from_label_or_proba(label: Optional[str], proba: Optional[float]) -> Optional[float]:
        """
        Priority:
          1) If score_map.json has a mapping for label -> score, use it.
          2) Else, if proba exists, convert confidence into 0-10 range safely.
          3) Else return None.
        """
        sm = InterviewAIModelService._score_map or {}

        if label is not None:
            # score_map.json can be like:
            # {"GOOD": 8, "AVERAGE": 5, "POOR": 2}
            if isinstance(sm, dict) and label in sm:
                try:
                    return round(float(sm[label]), 2)
                except Exception:
                    pass

            # Some people store nested config:
            # {"map": {"GOOD": 8, ...}}
            if isinstance(sm, dict) and "map" in sm and isinstance(sm["map"], dict) and label in sm["map"]:
                try:
                    return round(float(sm["map"][label]), 2)
                except Exception:
                    pass

        # Confidence fallback (very simple)
        if isinstance(proba, (int, float)):
            # map [0.0..1.0] -> [3..10] (avoid giving 0 unless transcript is empty)
            score = 3.0 + 7.0 * float(proba)
            return round(max(0.0, min(10.0, score)), 2)

        return None