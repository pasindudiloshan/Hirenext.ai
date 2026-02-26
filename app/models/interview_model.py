# app/models/interview_model.py
# HireNext.ai — Interview DB Model (Mongo Layer Only)
#
# This file ONLY talks to MongoDB.
# All business logic lives in interview_service.py

from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId
from flask import current_app


class InterviewModel:
    """
    MongoDB model for scheduled interviews.

    Collection: interviews
    One document = one candidate interview slot
    """

    COLLECTION = "interviews"

    # --------------------------------------------------
    # Internal helper
    # --------------------------------------------------
    @staticmethod
    def _db():
        return current_app.mongo.db

    @staticmethod
    def _oid(val: str) -> Optional[ObjectId]:
        try:
            return ObjectId(val)
        except Exception:
            return None

    # --------------------------------------------------
    # CREATE
    # --------------------------------------------------
    @staticmethod
    def insert_many(interviews: List[Dict]) -> bool:
        """Bulk insert interview documents."""
        if not interviews:
            return False
        try:
            InterviewModel._db()[InterviewModel.COLLECTION].insert_many(interviews)
            return True
        except Exception:
            return False

    # --------------------------------------------------
    # READ
    # --------------------------------------------------
    @staticmethod
    def get_by_id(interview_id: str) -> Optional[Dict]:
        oid = InterviewModel._oid(interview_id)
        if not oid:
            return None
        return InterviewModel._db()[InterviewModel.COLLECTION].find_one({"_id": oid})

    @staticmethod
    def get_by_batch(batch_id: str) -> List[Dict]:
        """All interviews for a batch (any date)."""
        return list(
            InterviewModel._db()[InterviewModel.COLLECTION]
            .find({"batch_id": str(batch_id)})
            .sort([("date", 1), ("start_time", 1)])
        )

    @staticmethod
    def get_by_batch_and_date(batch_id: str, date_iso: str) -> List[Dict]:
        """Interviews for a batch on a specific date (YYYY-MM-DD)."""
        return list(
            InterviewModel._db()[InterviewModel.COLLECTION]
            .find({"batch_id": str(batch_id), "date": date_iso})
            .sort("start_time", 1)
        )

    @staticmethod
    def get_between_dates(
        start_date: str,
        end_date: str,
        batch_id: Optional[str] = None
    ) -> List[Dict]:
        """Calendar queries (month / week / range)."""
        q: Dict = {"date": {"$gte": start_date, "$lte": end_date}}
        if batch_id:
            q["batch_id"] = str(batch_id)

        return list(
            InterviewModel._db()[InterviewModel.COLLECTION]
            .find(q)
            .sort([("date", 1), ("start_time", 1)])
        )

    # --------------------------------------------------
    # UPDATE
    # --------------------------------------------------
    @staticmethod
    def mark_invites_sent(batch_id: str, date_iso: str, emails: List[str]) -> int:
        """
        Marks invite_sent=True for given candidate emails.
        Returns number of updated documents.
        """
        if not emails:
            return 0

        res = InterviewModel._db()[InterviewModel.COLLECTION].update_many(
            {"batch_id": str(batch_id), "date": date_iso, "candidate_email": {"$in": emails}},
            {"$set": {"invite_sent": True, "invite_sent_at": datetime.now(timezone.utc)}}
        )
        return int(res.modified_count or 0)

    @staticmethod
    def update_meeting_link(batch_id: str, link: str) -> int:
        """Updates meeting link for all interviews in a batch."""
        res = InterviewModel._db()[InterviewModel.COLLECTION].update_many(
            {"batch_id": str(batch_id)},
            {"$set": {"meeting_link": link}}
        )
        return int(res.modified_count or 0)

    @staticmethod
    def cancel_interview(interview_id: str) -> bool:
        """Soft delete (status = CANCELLED)."""
        oid = InterviewModel._oid(interview_id)
        if not oid:
            return False

        res = InterviewModel._db()[InterviewModel.COLLECTION].update_one(
            {"_id": oid},
            {"$set": {"status": "CANCELLED", "cancelled_at": datetime.now(timezone.utc)}}
        )
        return (res.modified_count == 1)

    # --------------------------------------------------
    # DELETE (rarely used)
    # --------------------------------------------------
    @staticmethod
    def delete_by_batch(batch_id: str) -> int:
        """Deletes all interviews under a batch. Useful if batch is reset."""
        res = InterviewModel._db()[InterviewModel.COLLECTION].delete_many({"batch_id": str(batch_id)})
        return int(res.deleted_count or 0)

    # --------------------------------------------------
    # STATS / COUNTS
    # --------------------------------------------------
    @staticmethod
    def count_by_batch(batch_id: str) -> int:
        return int(
            InterviewModel._db()[InterviewModel.COLLECTION].count_documents({"batch_id": str(batch_id)}) or 0
        )

    @staticmethod
    def count_by_batch_and_date(batch_id: str, date_iso: str) -> int:
        return int(
            InterviewModel._db()[InterviewModel.COLLECTION].count_documents(
                {"batch_id": str(batch_id), "date": date_iso}
            ) or 0
        )