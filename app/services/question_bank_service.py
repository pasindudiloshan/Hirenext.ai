# app/services/question_bank_service.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class BankLoadResult:
    ok: bool
    bank: Dict[str, List[Dict[str, Any]]]
    error: Optional[str] = None
    path: Optional[str] = None
    warnings: Optional[List[str]] = None


class QuestionBankService:
    """
    Loads interview question bank from:
      app/data/interview_QA_bank.json

    Expected JSON shape:
      {
        "Role Name": [
          {
            "id": "ROLE_Q1",
            "question": "....",
            "rubric": [ {"point": "...", "score": 4}, ... ],
            "correctness": { ... optional ... }
          },
          ...
        ],
        ...
      }

    Safe behavior:
    - If file does not exist yet: returns empty roles/questions (no crash).
    - Provides validate helpers to catch common mistakes early.
    - Supports forgiving role matching (case-insensitive + trimmed).
    """

    DEFAULT_FILENAME = "interview_QA_bank.json"

    # ----------------------------
    # Role normalization
    # ----------------------------
    @staticmethod
    def normalize_role(role: str) -> str:
        """
        Normalize role names for lookup.
        (Keeps it conservative: only whitespace + lower)
        """
        return " ".join((role or "").strip().split()).lower()

    # ----------------------------
    # Path helpers
    # ----------------------------
    @staticmethod
    def _bank_path() -> str:
        """
        Resolve absolute path to app/data/interview_QA_bank.json
        Works regardless of where app is executed from.
        """
        services_dir = os.path.dirname(os.path.abspath(__file__))  # app/services
        app_dir = os.path.dirname(services_dir)                    # app/
        data_dir = os.path.join(app_dir, "data")                   # app/data
        return os.path.join(data_dir, QuestionBankService.DEFAULT_FILENAME)

    # ----------------------------
    # Load + cache
    # ----------------------------
    @staticmethod
    @lru_cache(maxsize=1)
    def _load_bank_cached() -> BankLoadResult:
        """
        Cached bank loader (single process cache).
        If you edit JSON while server is running, call reload_bank().
        """
        path = QuestionBankService._bank_path()

        if not os.path.exists(path):
            return BankLoadResult(
                ok=False,
                bank={},
                error=f"Question bank file not found at: {path}",
                path=path,
                warnings=[],
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            return BankLoadResult(
                ok=False,
                bank={},
                error=f"Invalid JSON in question bank: {e}",
                path=path,
                warnings=[],
            )
        except Exception as e:
            return BankLoadResult(
                ok=False,
                bank={},
                error=f"Failed to read question bank: {e}",
                path=path,
                warnings=[],
            )

        bank = QuestionBankService._normalize_bank(raw)
        ok, err, warnings = QuestionBankService.validate_bank(bank)

        return BankLoadResult(
            ok=ok,
            bank=bank,
            error=err,
            path=path,
            warnings=warnings,
        )

    @staticmethod
    def reload_bank() -> BankLoadResult:
        """
        Clear cache and reload from disk.
        Call this after editing interview_QA_bank.json without restarting server.
        """
        try:
            QuestionBankService._load_bank_cached.cache_clear()
        except Exception:
            pass
        return QuestionBankService._load_bank_cached()

    @staticmethod
    def load_bank() -> BankLoadResult:
        """Get the cached bank load result."""
        return QuestionBankService._load_bank_cached()

    # ----------------------------
    # Public API
    # ----------------------------
    @staticmethod
    def get_roles() -> List[str]:
        res = QuestionBankService.load_bank()
        roles = sorted([str(k) for k in (res.bank or {}).keys()])
        return roles

    @staticmethod
    def _resolve_role_key(role: str) -> Optional[str]:
        """
        Finds the best matching role key inside the JSON bank.
        Matching order:
          1) exact
          2) normalized (case-insensitive + trimmed)
        """
        role = (role or "").strip()
        if not role:
            return None

        res = QuestionBankService.load_bank()
        bank = res.bank or {}

        # 1) exact
        if role in bank:
            return role

        # 2) normalized match
        target = QuestionBankService.normalize_role(role)
        for k in bank.keys():
            if QuestionBankService.normalize_role(k) == target:
                return k

        return None

    @staticmethod
    def get_questions_for_role(role: str) -> List[Dict[str, Any]]:
        role = (role or "").strip()
        if not role:
            return []

        res = QuestionBankService.load_bank()
        key = QuestionBankService._resolve_role_key(role)
        if not key:
            return []

        qs = (res.bank or {}).get(key) or []
        return [dict(q) for q in qs if isinstance(q, dict)]

    @staticmethod
    def get_question(role: str, question_id: str) -> Optional[Dict[str, Any]]:
        role = (role or "").strip()
        question_id = (question_id or "").strip()

        if not role or not question_id:
            return None

        qs = QuestionBankService.get_questions_for_role(role)
        for q in qs:
            if str(q.get("id", "")).strip() == question_id:
                return dict(q)
        return None

    @staticmethod
    def find_question_by_id(question_id: str) -> Optional[Dict[str, Any]]:
        """
        Useful debugging helper: find a question by id across ALL roles.
        """
        qid = (question_id or "").strip()
        if not qid:
            return None

        res = QuestionBankService.load_bank()
        for role, qs in (res.bank or {}).items():
            if not isinstance(qs, list):
                continue
            for q in qs:
                if isinstance(q, dict) and str(q.get("id", "")).strip() == qid:
                    out = dict(q)
                    out["_role"] = role
                    return out
        return None

    @staticmethod
    def get_question_or_raise(role: str, question_id: str) -> Dict[str, Any]:
        q = QuestionBankService.get_question(role, question_id)
        if q is None:
            # Debug aid: try global search
            found = QuestionBankService.find_question_by_id(question_id)
            if found:
                raise KeyError(
                    f"Question id='{question_id}' exists under role='{found.get('_role')}', "
                    f"but not under requested role='{role}'. Role mismatch."
                )
            raise KeyError(f"Question not found for role='{role}' id='{question_id}'")
        return q

    # ----------------------------
    # Normalize + validate
    # ----------------------------
    @staticmethod
    def _normalize_bank(raw: Any) -> Dict[str, List[Dict[str, Any]]]:
        """
        Best-effort normalization:
        - Ensures dict[str, list[dict]]
        - Strips role names
        - Ensures each question has id/question fields (if present)
        """
        if not isinstance(raw, dict):
            return {}

        out: Dict[str, List[Dict[str, Any]]] = {}
        for role, items in raw.items():
            r = str(role).strip()
            if not r:
                continue

            if not isinstance(items, list):
                continue

            norm_items: List[Dict[str, Any]] = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                q = dict(it)

                # normalize keys we rely on
                q["id"] = str(q.get("id") or "").strip()
                q["question"] = str(q.get("question") or "").strip()

                # optional fields
                if "skill" in q:
                    q["skill"] = str(q.get("skill") or "").strip()
                if "difficulty" in q:
                    q["difficulty"] = str(q.get("difficulty") or "").strip()

                # rubric normalization (list of {point, score})
                rb = q.get("rubric")
                if isinstance(rb, list):
                    new_rb = []
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
                    q["rubric"] = new_rb
                else:
                    q["rubric"] = []

                norm_items.append(q)

            out[r] = norm_items

        return out

    @staticmethod
    def validate_bank(bank: Dict[str, List[Dict[str, Any]]]) -> Tuple[bool, Optional[str], List[str]]:
        """
        Minimal validation:
        - bank is dict[role] -> list
        - each question has non-empty id + question
        - rubric scores should sum to ~10 (WARNING only)
        """
        warnings: List[str] = []

        if not isinstance(bank, dict) or not bank:
            # allow boot with empty bank, but flag as not ok
            return False, "Question bank is empty or invalid (create app/data/interview_QA_bank.json).", warnings

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

                # WARNING only: rubric sum
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