# app/models/shortlisted_batch_model.py

from datetime import datetime
from bson import ObjectId
from flask import current_app


class ShortlistedBatchModel:
    """
    DB layer for screening_batches collection.
    We persist ONLY shortlisted candidates inside a batch.
    """

    COLLECTION = "screening_batches"

    @staticmethod
    def create_batch(job: dict):
        db = current_app.mongo.db
        now = datetime.utcnow()

        batch_doc = {
            "job_id": str(job["_id"]),
            "job_title": job.get("job_title", ""),
            "created_at": now,
            "status": "ACTIVE",
            "shortlisted_candidates": []
        }
        return db[ShortlistedBatchModel.COLLECTION].insert_one(batch_doc)

    @staticmethod
    def get_batch_by_id(batch_id: str):
        db = current_app.mongo.db
        try:
            return db[ShortlistedBatchModel.COLLECTION].find_one({"_id": ObjectId(batch_id)})
        except Exception:
            return None

    @staticmethod
    def get_active_batch(batch_id: str):
        db = current_app.mongo.db
        try:
            return db[ShortlistedBatchModel.COLLECTION].find_one({
                "_id": ObjectId(batch_id),
                "status": "ACTIVE"
            })
        except Exception:
            return None

    @staticmethod
    def close_batch(batch_id: str):
        db = current_app.mongo.db
        try:
            return db[ShortlistedBatchModel.COLLECTION].update_one(
                {"_id": ObjectId(batch_id), "status": "ACTIVE"},
                {"$set": {"status": "CLOSED", "closed_at": datetime.utcnow()}}
            )
        except Exception:
            return None

    @staticmethod
    def save_shortlisted(batch_id: str, shortlisted_docs: list):
        db = current_app.mongo.db
        now = datetime.utcnow()

        try:
            return db[ShortlistedBatchModel.COLLECTION].update_one(
                {"_id": ObjectId(batch_id), "status": "ACTIVE"},
                {
                    "$push": {"shortlisted_candidates": {"$each": shortlisted_docs}},
                    "$set": {"status": "SHORTLISTED", "shortlisted_at": now}
                }
            )
        except Exception:
            return None