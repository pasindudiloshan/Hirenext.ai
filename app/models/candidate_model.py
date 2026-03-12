from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app


class CandidateModel:
    @staticmethod
    def collection():
        return current_app.mongo.db.candidates

    @staticmethod
    def find_all() -> List[Dict[str, Any]]:
        return list(CandidateModel.collection().find().sort("created_at", -1))

    @staticmethod
    def find_by_email(email: str) -> Optional[Dict[str, Any]]:
        return CandidateModel.collection().find_one({
            "email": email.strip().lower()
        })

    @staticmethod
    def find_by_id(object_id: Any) -> Optional[Dict[str, Any]]:
        return CandidateModel.collection().find_one({"_id": object_id})

    @staticmethod
    def create(doc: Dict[str, Any]):
        return CandidateModel.collection().insert_one(doc)

    @staticmethod
    def update_by_id(object_id: Any, update_data: Dict[str, Any]):
        update_data["updated_at"] = datetime.utcnow()
        return CandidateModel.collection().update_one(
            {"_id": object_id},
            {"$set": update_data}
        )

    @staticmethod
    def delete_by_id(object_id: Any):
        return CandidateModel.collection().delete_one({"_id": object_id})

    @staticmethod
    def count_all() -> int:
        return CandidateModel.collection().count_documents({})