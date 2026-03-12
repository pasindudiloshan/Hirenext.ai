from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from werkzeug.security import check_password_hash, generate_password_hash

from app.models.staff_model import StaffModel
from app.models.candidate_model import CandidateModel


class AuthService:
    @staticmethod
    def register_candidate(
        full_name: str,
        email: str,
        password: str
    ) -> Tuple[bool, str]:
        """
        Register a new candidate account.
        """
        full_name = full_name.strip()
        email = email.strip().lower()
        password = password.strip()

        if not full_name or not email or not password:
            return False, "All fields are required."

        if len(password) < 8:
            return False, "Password must be at least 8 characters."

        existing_candidate = CandidateModel.find_by_email(email)
        if existing_candidate:
            return False, "A candidate account with this email already exists."

        existing_staff = StaffModel.find_by_email(email)
        if existing_staff:
            return False, "This email is already used by a staff account."

        now = datetime.utcnow()

        doc = {
            "full_name": full_name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": "candidate",
            "status": "Active",
            "is_active": True,
            "last_active": "Never",
            "created_at": now,
            "updated_at": now,
        }

        CandidateModel.create(doc)
        return True, "Registration successful! Please login."

    @staticmethod
    def login_candidate(email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify candidate login.
        """
        email = email.strip().lower()
        password = password.strip()

        if not email or not password:
            return None

        candidate = CandidateModel.find_by_email(email)
        if not candidate:
            return None

        if str(candidate.get("status", "Active")).strip().lower() != "active":
            return None

        password_hash = str(candidate.get("password_hash", "")).strip()
        if not password_hash:
            return None

        if not check_password_hash(password_hash, password):
            return None

        CandidateModel.update_by_id(
            candidate["_id"],
            {"last_active": "Just now"}
        )

        updated_candidate = CandidateModel.find_by_id(candidate["_id"])
        if not updated_candidate:
            return None

        return AuthService._normalize_candidate_login_doc(updated_candidate)

    @staticmethod
    def login_staff(email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify staff login.
        """
        email = email.strip().lower()
        password = password.strip()

        if not email or not password:
            return None

        staff = StaffModel.find_by_email(email)
        if not staff:
            return None

        if str(staff.get("status", "Active")).strip().lower() != "active":
            return None

        password_hash = str(staff.get("password_hash", "")).strip()
        if not password_hash:
            return None

        if not check_password_hash(password_hash, password):
            return None

        StaffModel.update_by_id(
            staff["_id"],
            {"last_active": "Just now"}
        )

        updated_staff = StaffModel.find_by_id(staff["_id"])
        if not updated_staff:
            return None

        return AuthService._normalize_staff_login_doc(updated_staff)

    @staticmethod
    def get_candidate_by_email(email: str) -> Optional[Dict[str, Any]]:
        """
        Get candidate by email.
        """
        email = email.strip().lower()
        if not email:
            return None

        candidate = CandidateModel.find_by_email(email)
        if not candidate:
            return None

        return AuthService._normalize_candidate_full_doc(candidate)

    @staticmethod
    def get_staff_by_email(email: str) -> Optional[Dict[str, Any]]:
        """
        Get staff by email.
        """
        email = email.strip().lower()
        if not email:
            return None

        staff = StaffModel.find_by_email(email)
        if not staff:
            return None

        return AuthService._normalize_staff_full_doc(staff)

    @staticmethod
    def generate_password_hash_value(password: str) -> str:
        """
        Helper method to generate password hash.
        """
        return generate_password_hash(password.strip())

    @staticmethod
    def verify_password(password_hash: str, password: str) -> bool:
        """
        Helper method to verify password against stored hash.
        """
        password_hash = password_hash.strip()
        password = password.strip()

        if not password_hash or not password:
            return False

        return check_password_hash(password_hash, password)

    @staticmethod
    def _normalize_candidate_login_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Candidate login response object for session use.
        """
        return {
            "id": str(doc.get("_id", "")),
            "full_name": doc.get("full_name", ""),
            "email": doc.get("email", ""),
            "role": doc.get("role", "candidate"),
            "status": doc.get("status", "Active"),
            "last_active": doc.get("last_active", "Never"),
        }

    @staticmethod
    def _normalize_staff_login_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Staff login response object for session use.
        """
        return {
            "id": str(doc.get("_id", "")),
            "full_name": doc.get("full_name", ""),
            "email": doc.get("email", ""),
            "role": doc.get("role", "staff"),
            "organization": doc.get("organization", ""),
            "status": doc.get("status", "Active"),
            "last_active": doc.get("last_active", "Never"),
        }

    @staticmethod
    def _normalize_candidate_full_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full candidate object.
        """
        created_at = doc.get("created_at")
        updated_at = doc.get("updated_at")

        if isinstance(created_at, datetime):
            created_at = created_at.strftime("%Y-%m-%d %H:%M")
        else:
            created_at = created_at or "-"

        if isinstance(updated_at, datetime):
            updated_at = updated_at.strftime("%Y-%m-%d %H:%M")
        else:
            updated_at = updated_at or "-"

        return {
            "id": str(doc.get("_id", "")),
            "full_name": doc.get("full_name", ""),
            "email": doc.get("email", ""),
            "role": doc.get("role", "candidate"),
            "status": doc.get("status", "Active"),
            "is_active": doc.get("is_active", True),
            "last_active": doc.get("last_active", "Never"),
            "created_at": created_at,
            "updated_at": updated_at,
        }

    @staticmethod
    def _normalize_staff_full_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full staff object.
        """
        created_at = doc.get("created_at")
        updated_at = doc.get("updated_at")

        if isinstance(created_at, datetime):
            created_at = created_at.strftime("%Y-%m-%d %H:%M")
        else:
            created_at = created_at or "-"

        if isinstance(updated_at, datetime):
            updated_at = updated_at.strftime("%Y-%m-%d %H:%M")
        else:
            updated_at = updated_at or "-"

        return {
            "id": str(doc.get("_id", "")),
            "staff_code": doc.get("staff_code", ""),
            "full_name": doc.get("full_name", ""),
            "role": doc.get("role", "staff"),
            "email": doc.get("email", ""),
            "organization": doc.get("organization", ""),
            "status": doc.get("status", "Active"),
            "is_active": doc.get("is_active", True),
            "last_active": doc.get("last_active", "Never"),
            "created_at": created_at,
            "updated_at": updated_at,
        }