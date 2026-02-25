# app/__init__.py
import os
from flask import Flask
from flask_pymongo import PyMongo

mongo = PyMongo()

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Load config
    app.config.from_object("app.config.Config")

    # Secret key
    app.secret_key = app.config.get("SECRET_KEY") or os.environ.get("SECRET_KEY", "super-secret-hirenext-key")

    # Init Mongo
    mongo.init_app(app)
    app.mongo = mongo

    # ------------------------
    # Register Blueprints
    # ------------------------
    from app.controllers.job_controller import job_bp
    from app.controllers.resume_controller import resume_bp
    from app.controllers.interview_controller import interview_bp

    app.register_blueprint(job_bp)  # ✅ NO PREFIX
    app.register_blueprint(resume_bp, url_prefix="/screening")
    app.register_blueprint(interview_bp, url_prefix="/interview")

    # ------------------------
    # Health Check
    # ------------------------
    @app.route("/health")
    def health():
        return {"status": "ok", "db": mongo.db.name}

    return app