# app/services/semantic_service.py
from __future__ import annotations

from functools import lru_cache
from sentence_transformers import SentenceTransformer, util


class SemanticMatcher:
    """
    Semantic similarity scorer for:
      resume_text  vs  job_description

    Uses SentenceTransformer embeddings + cosine similarity (same core idea as your notebook).
    Designed for Flask use (cache JD embeddings).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    @lru_cache(maxsize=256)
    def _encode_cached(self, text: str):
        """
        Cache encodings for repeated texts (JD repeats often, resumes usually don't).
        NOTE: lru_cache works because 'text' is hashable.
        """
        return self.model.encode(text, convert_to_tensor=True)

    def semantic_similarity(self, a: str, b: str) -> float:
        """
        Returns cosine similarity in range [0..1] (clipped).
        """
        if not a or not b:
            return 0.0

        emb_a = self.model.encode(a, convert_to_tensor=True)
        emb_b = self._encode_cached(b)

        sim = util.pytorch_cos_sim(emb_a, emb_b).item()  # typically ~0..1
        sim = float(sim)

        # clip to [0..1]
        if sim < 0:
            sim = 0.0
        if sim > 1:
            sim = 1.0

        return round(sim, 4)

    def semantic_score_0_100(self, resume_text: str, job_description: str) -> float:
        """
        Returns a semantic match score scaled to [0..100].
        """
        sim = self.semantic_similarity(resume_text, job_description)
        return round(sim * 100.0, 2)