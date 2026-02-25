# app/models/job_model.py

from datetime import datetime
from bson import ObjectId
from flask import current_app


class JobModel:

    @staticmethod
    def create(job_data: dict):
        db = current_app.mongo.db
        job_data["created_at"] = datetime.utcnow()
        job_data["updated_at"] = datetime.utcnow()
        job_data["is_active"] = True
        return db.jobs.insert_one(job_data)

    @staticmethod
    def get_all():
        db = current_app.mongo.db
        return list(db.jobs.find().sort("created_at", -1))

    @staticmethod
    def get_by_id(job_id: str):
        db = current_app.mongo.db
        try:
            return db.jobs.find_one({"_id": ObjectId(job_id)})
        except Exception:
            return None

    @staticmethod
    def update(job_id: str, update_data: dict):
        db = current_app.mongo.db
        update_data["updated_at"] = datetime.utcnow()
        return db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_data}
        )

    @staticmethod
    def delete(job_id: str):
        db = current_app.mongo.db
        return db.jobs.delete_one({"_id": ObjectId(job_id)})

    @staticmethod
    def toggle_active(job_id: str, status: bool):
        db = current_app.mongo.db
        return db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {
                "is_active": status,
                "updated_at": datetime.utcnow()
            }}
        )