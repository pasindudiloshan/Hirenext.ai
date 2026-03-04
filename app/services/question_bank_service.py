# app/services/question_bank_service.py  ✅ MongoDB-backed (no JSON file)
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app


@dataclass(frozen=True)
class BankLoadResult:
    """
    Kept for compatibility with your older code style.
    Now reflects Mongo status instead of JSON file status.
    """
    ok: bool
    bank: Dict[str, List[Dict[str, Any]]]
    error: Optional[str] = None
    path: Optional[str] = None
    warnings: Optional[List[str]] = None


class QuestionBankService:
    """
    ✅ MongoDB question bank service

    Collection: question_bank

    Expected document shape (per question):
      {
        "role": "Senior Accountant",
        "question_id": "SA_Q1",
        "question": "...",
        "skill": "...",
        "difficulty": "...",
        "rubric": [ {"point": "...", "score": 4}, ... ],
        "correctness": { ... },
        "is_active": true
      }

    Notes:
    - No JSON file, no lru_cache, no reload needed
    - Role matching supports:
        exact role
        normalized role (case/whitespace)
    """

    COLLECTION = "question_bank"
    DEFAULT_QUESTION_LIMIT = 5

    # ----------------------------
    # DB helpers
    # ----------------------------
    @staticmethod
    def _db():
        return current_app.mongo.db

    # ----------------------------
    # Role normalization
    # ----------------------------
    @staticmethod
    def normalize_role(role: str) -> str:
        """Normalize role names for matching (lower + collapse whitespace)."""
        return " ".join((role or "").strip().split()).lower()

    @staticmethod
    def _resolve_role_key(role: str) -> Optional[str]:
        """
        Finds best matching role in DB.
        Matching order:
          1) exact match (case-sensitive)
          2) normalized match (case-insensitive + trimmed)
        """
        role = (role or "").strip()
        if not role:
            return None

        db = QuestionBankService._db()
        col = db[QuestionBankService.COLLECTION]

        # 1) exact (fast check)
        if col.find_one({"role": role, "is_active": True}, projection={"_id": 1}):
            return role

        # 2) normalized match
        target = QuestionBankService.normalize_role(role)

        # Get distinct roles that exist (active only)
        try:
            roles = col.distinct("role", {"is_active": True}) or []
        except Exception:
            roles = []

        for r in roles:
            if QuestionBankService.normalize_role(str(r)) == target:
                return str(r)

        return None

    # ----------------------------
    # Document -> Question dict
    # ----------------------------
    @staticmethod
    def _to_question(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Mongo doc into the shape used across your app.
        Ensures keys:
          id, question, skill, difficulty, rubric, correctness
        """
        if not isinstance(doc, dict):
            return {}

        # rubric normalization
        rb = doc.get("rubric") or []
        new_rb: List[Dict[str, Any]] = []
        if isinstance(rb, list):
            for p in rb:
                if isinstance(p, dict):
                    point = str(p.get("point") or "").strip()
                    score = p.get("score", 0)
                    try:
                        score = float(score)
                    except Exception:
                        score = 0.0
                    if point:
                        new_rb.append({"point": point, "score": score})

        correctness = doc.get("correctness") or {}
        if not isinstance(correctness, dict):
            correctness = {}

        return {
            "id": str(doc.get("question_id") or doc.get("id") or "").strip(),
            "question": str(doc.get("question") or "").strip(),
            "skill": str(doc.get("skill") or "").strip(),
            "difficulty": str(doc.get("difficulty") or "").strip(),
            "rubric": new_rb,
            "correctness": correctness,
        }

    # ----------------------------
    # Public API
    # ----------------------------
    @staticmethod
    def get_roles() -> List[str]:
        """Return all active roles that have active questions."""
        db = QuestionBankService._db()
        col = db[QuestionBankService.COLLECTION]
        try:
            roles = col.distinct("role", {"is_active": True}) or []
        except Exception:
            roles = []
        return sorted([str(r) for r in roles if str(r).strip()])

    @staticmethod
    def get_questions_for_role(
        role: str,
        limit: Optional[int] = None,
        *,
        random_pick: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Return questions for a role.

        - limit: max number of questions (default = DEFAULT_QUESTION_LIMIT)
        - random_pick: if True, randomly sample questions (good for real interviews)
        """
        role = (role or "").strip()
        if not role:
            return []

        resolved = QuestionBankService._resolve_role_key(role)
        if not resolved:
            return []

        db = QuestionBankService._db()
        col = db[QuestionBankService.COLLECTION]

        # Fetch active questions for role
        docs = list(col.find(
            {"role": resolved, "is_active": True},
            projection={
                "_id": 0,
                "role": 1,
                "question_id": 1,
                "id": 1,
                "question": 1,
                "skill": 1,
                "difficulty": 1,
                "rubric": 1,
                "correctness": 1,
            }
        ))

        qs = [QuestionBankService._to_question(d) for d in docs]
        qs = [q for q in qs if q.get("id") and q.get("question")]

        # Apply limit
        n = QuestionBankService.DEFAULT_QUESTION_LIMIT if limit is None else int(limit)
        if n <= 0:
            return qs

        if random_pick and len(qs) > n:
            # built-in random sampling (no extra imports outside function)
            import random
            return random.sample(qs, n)

        return qs[:n]

    @staticmethod
    def get_question(role: str, question_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single question by role + question_id."""
        role = (role or "").strip()
        question_id = (question_id or "").strip()
        if not role or not question_id:
            return None

        resolved = QuestionBankService._resolve_role_key(role)
        if not resolved:
            return None

        db = QuestionBankService._db()
        col = db[QuestionBankService.COLLECTION]

        doc = col.find_one(
            {"role": resolved, "question_id": question_id, "is_active": True},
            projection={"_id": 0}
        )

        if not doc:
            # fallback: maybe stored as "id" instead of "question_id"
            doc = col.find_one(
                {"role": resolved, "id": question_id, "is_active": True},
                projection={"_id": 0}
            )

        return QuestionBankService._to_question(doc) if doc else None

    @staticmethod
    def find_question_by_id(question_id: str) -> Optional[Dict[str, Any]]:
        """
        Debug helper: find by question_id across ALL roles.
        Returns question + _role if found.
        """
        qid = (question_id or "").strip()
        if not qid:
            return None

        db = QuestionBankService._db()
        col = db[QuestionBankService.COLLECTION]

        doc = col.find_one(
            {"question_id": qid, "is_active": True},
            projection={"_id": 0}
        )
        if not doc:
            doc = col.find_one(
                {"id": qid, "is_active": True},
                projection={"_id": 0}
            )

        if not doc:
            return None

        out = QuestionBankService._to_question(doc)
        out["_role"] = str(doc.get("role") or "")
        return out

    @staticmethod
    def get_question_or_raise(role: str, question_id: str) -> Dict[str, Any]:
        q = QuestionBankService.get_question(role, question_id)
        if q is None:
            found = QuestionBankService.find_question_by_id(question_id)
            if found:
                raise KeyError(
                    f"Question id='{question_id}' exists under role='{found.get('_role')}', "
                    f"but not under requested role='{role}'. Role mismatch."
                )
            raise KeyError(f"Question not found for role='{role}' id='{question_id}'")
        return q

    # ----------------------------
    # Optional: Health / Validation
    # ----------------------------
    @staticmethod
    def load_bank() -> BankLoadResult:
        """
        Compatibility method: returns a pseudo 'bank' grouped by role.
        Avoid using this for runtime interview flow (DB queries are better).
        """
        try:
            roles = QuestionBankService.get_roles()
            bank: Dict[str, List[Dict[str, Any]]] = {}
            for r in roles:
                bank[r] = QuestionBankService.get_questions_for_role(r, limit=10_000)
            ok, err, warnings = QuestionBankService.validate_bank(bank)
            return BankLoadResult(ok=ok, bank=bank, error=err, warnings=warnings)
        except Exception as e:
            return BankLoadResult(ok=False, bank={}, error=str(e), warnings=[])

    @staticmethod
    def validate_bank(bank: Dict[str, List[Dict[str, Any]]]) -> Tuple[bool, Optional[str], List[str]]:
        """
        Minimal validation (same spirit as your JSON version).
        """
        warnings: List[str] = []
        if not isinstance(bank, dict) or not bank:
            return False, "Question bank is empty or invalid in MongoDB.", warnings

        seen_ids = set()
        for role, qs in bank.items():
            if not isinstance(qs, list):
                return False, f"Role '{role}' must map to a list of questions.", warnings

            for i, q in enumerate(qs):
                if not isinstance(q, dict):
                    return False, f"Role '{role}' question #{i+1} must be an object.", warnings

                qid = str(q.get("id") or "").strip()
                qt = str(q.get("question") or "").strip()

                if not qid:
                    return False, f"Role '{role}' question #{i+1} is missing 'id'.", warnings
                if not qt:
                    return False, f"Role '{role}' question '{qid}' is missing 'question'.", warnings

                if qid in seen_ids:
                    warnings.append(f"Duplicate question id detected: '{qid}' (role '{role}').")
                seen_ids.add(qid)

                rb = q.get("rubric") or []
                if not isinstance(rb, list):
                    return False, f"Role '{role}' question '{qid}' rubric must be a list.", warnings

                total = 0.0
                for p in rb:
                    if isinstance(p, dict):
                        try:
                            total += float(p.get("score", 0))
                        except Exception:
                            pass

                if rb and (total < 6 or total > 14):
                    warnings.append(
                        f"Rubric total for role '{role}' question '{qid}' should be ~10. Current total = {total:.1f}"
                    )

        return True, None, warnings