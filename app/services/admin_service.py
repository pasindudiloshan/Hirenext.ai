from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.models.staff_model import StaffModel


class AdminService:
    @staticmethod
    def verify_admin_login(email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify fixed admin credentials from config using plain text.
        """
        admin_email = str(current_app.config.get("ADMIN_EMAIL", "")).strip().lower()
        admin_password = str(current_app.config.get("ADMIN_PASSWORD", "")).strip()

        email = email.strip().lower()
        password = password.strip()

        if not admin_email or not admin_password:
            return None

        if not email or not password:
            return None

        if email != admin_email:
            return None

        if password != admin_password:
            return None

        return {
            "id": "admin-1",
            "username": "Admin",
            "email": admin_email,
            "role": "admin"
        }

    @staticmethod
    def get_dashboard_counts() -> Dict[str, int]:
        """
        Get summary statistics for admin dashboard.
        """
        db = current_app.mongo.db

        return {
            "total_staff": StaffModel.count_all(),
            "total_vacancies": db.jobs.count_documents({}),
            "total_orgs": db.organizations.count_documents({}),
            "active_recruiters": StaffModel.count_active(),
            "total_candidates": db.candidates.count_documents({}),
        }

    @staticmethod
    def get_all_staff() -> List[Dict[str, Any]]:
        """
        Return all staff members sorted by newest first.
        """
        staff_docs = StaffModel.find_all()
        return [AdminService._normalize_staff_doc(staff) for staff in staff_docs]

    @staticmethod
    def get_staff_by_id(staff_id: Any) -> Optional[Dict[str, Any]]:
        """
        Find one staff member by MongoDB ObjectId.
        """
        try:
            object_id = ObjectId(staff_id)
        except Exception:
            return None

        doc = StaffModel.find_by_id(object_id)
        if not doc:
            return None

        return AdminService._normalize_staff_doc(doc)

    @staticmethod
    def get_staff_by_email(email: str) -> Optional[Dict[str, Any]]:
        """
        Find one staff member by email.
        """
        normalized_email = email.strip().lower()

        if not normalized_email:
            return None

        doc = StaffModel.find_by_email(normalized_email)
        if not doc:
            return None

        return AdminService._normalize_staff_doc(doc)

    @staticmethod
    def create_staff(
        full_name: str,
        role: str,
        email: str,
        organization: str,
        password: str,
        status: str = "Active"
    ) -> Tuple[bool, str]:
        """
        Create a new staff member.
        Staff passwords remain hashed in database.
        """
        full_name = full_name.strip()
        role = role.strip()
        email = email.strip().lower()
        organization = organization.strip()
        password = password.strip()
        status = status.strip() or "Active"

        if not full_name or not role or not email or not organization or not password:
            return False, "All staff fields are required."

        existing = StaffModel.find_by_email(email)
        if existing:
            return False, "A staff account with this email already exists."

        staff_code = AdminService._generate_staff_code()
        now = datetime.utcnow()

        doc = {
            "staff_code": staff_code,
            "full_name": full_name,
            "role": role,
            "email": email,
            "organization": organization,
            "password_hash": generate_password_hash(password),
            "status": status,
            "is_active": status.lower() == "active",
            "last_active": "Never",
            "created_at": now,
            "updated_at": now,
        }

        StaffModel.create(doc)
        return True, "Staff account created successfully."

    @staticmethod
    def update_staff(
        staff_id: Any,
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        email: Optional[str] = None,
        organization: Optional[str] = None,
        status: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Update staff member details.
        """
        try:
            object_id = ObjectId(staff_id)
        except Exception:
            return False, "Invalid staff ID."

        existing = StaffModel.find_by_id(object_id)
        if not existing:
            return False, "Staff member not found."

        update_data: Dict[str, Any] = {}

        if full_name is not None and full_name.strip():
            update_data["full_name"] = full_name.strip()

        if role is not None and role.strip():
            update_data["role"] = role.strip()

        if email is not None and email.strip():
            normalized_email = email.strip().lower()
            duplicate = StaffModel.find_by_email_excluding_id(normalized_email, object_id)
            if duplicate:
                return False, "Another account already uses this email."
            update_data["email"] = normalized_email

        if organization is not None and organization.strip():
            update_data["organization"] = organization.strip()

        if status is not None and status.strip():
            normalized_status = status.strip()
            update_data["status"] = normalized_status
            update_data["is_active"] = normalized_status.lower() == "active"

        if password is not None and password.strip():
            update_data["password_hash"] = generate_password_hash(password.strip())

        if not update_data:
            return False, "No valid fields provided for update."

        update_data["updated_at"] = datetime.utcnow()

        StaffModel.update_by_id(object_id, update_data)
        return True, "Staff details updated successfully."

    @staticmethod
    def delete_staff(staff_id: Any) -> Tuple[bool, str]:
        """
        Delete a staff member.
        """
        try:
            object_id = ObjectId(staff_id)
        except Exception:
            return False, "Invalid staff ID."

        existing = StaffModel.find_by_id(object_id)
        if not existing:
            return False, "Staff member not found."

        StaffModel.delete_by_id(object_id)
        return True, "Staff member deleted successfully."

    @staticmethod
    def toggle_staff_status(staff_id: Any) -> Tuple[bool, str]:
        """
        Toggle staff status between Active and Suspended.
        """
        try:
            object_id = ObjectId(staff_id)
        except Exception:
            return False, "Invalid staff ID."

        staff = StaffModel.find_by_id(object_id)
        if not staff:
            return False, "Staff member not found."

        current_status = str(staff.get("status", "Active")).strip().lower()
        new_status = "Suspended" if current_status == "active" else "Active"

        StaffModel.update_by_id(
            object_id,
            {
                "status": new_status,
                "is_active": new_status.lower() == "active",
                "updated_at": datetime.utcnow(),
            }
        )

        return True, f"Staff status changed to {new_status}."

    @staticmethod
    def verify_staff_login(email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify normal staff login using MongoDB staff collection.
        Staff passwords remain hashed.
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
            {
                "last_active": "Just now",
                "updated_at": datetime.utcnow(),
            }
        )

        updated_staff = StaffModel.find_by_id(staff["_id"])
        return AdminService._normalize_staff_doc(updated_staff) if updated_staff else None

    @staticmethod
    def _normalize_staff_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert MongoDB document into template-safe dictionary.
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
            "role": doc.get("role", ""),
            "email": doc.get("email", ""),
            "organization": doc.get("organization", ""),
            "status": doc.get("status", "Active"),
            "is_active": doc.get("is_active", True),
            "last_active": doc.get("last_active", "Never"),
            "created_at": created_at,
            "updated_at": updated_at,
        }

    @staticmethod
    def _generate_staff_code() -> str:
        """
        Generate incremental staff code like STF-001.
        """
        latest = StaffModel.get_latest_staff_code_doc()

        if not latest:
            return "STF-001"

        last_code = str(latest.get("staff_code", "STF-000")).strip()

        try:
            last_num = int(last_code.split("-")[-1])
            new_num = last_num + 1
        except Exception:
            new_num = StaffModel.count_all() + 1

        return f"STF-{new_num:03d}"

    @staticmethod
    def generate_password_hash_value(password: str) -> str:
        """
        Helper method to generate hashed password value for staff accounts.
        """
        return generate_password_hash(password.strip())