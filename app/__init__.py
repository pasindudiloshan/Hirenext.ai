import os
from flask import Flask, render_template
from flask_pymongo import PyMongo

mongo = PyMongo()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ------------------------
    # Load Config (app/config.py -> class Config)
    # ------------------------
    app.config.from_object("app.config.Config")

    # ------------------------
    # Secret Key (sessions/flash)
    # ------------------------
    app.secret_key = (
        app.config.get("SECRET_KEY")
        or os.environ.get("SECRET_KEY")
        or "super-secret-hirenext-key"
    )

    # ------------------------
    # ✅ SMTP Config (Gmail SMTP)
    # ------------------------
    app.config["SMTP_HOST"] = (
        app.config.get("SMTP_HOST")
        or os.environ.get("SMTP_HOST")
        or "smtp.gmail.com"
    )

    app.config["SMTP_PORT"] = int(
        app.config.get("SMTP_PORT")
        or os.environ.get("SMTP_PORT")
        or 587
    )

    app.config["SMTP_USER"] = (
        app.config.get("SMTP_USER")
        or os.environ.get("SMTP_USER")
        or ""
    )

    app.config["SMTP_PASS"] = (
        app.config.get("SMTP_PASS")
        or os.environ.get("SMTP_PASS")
        or ""
    )

    # FROM_EMAIL is optional; defaults to SMTP_USER
    app.config["FROM_EMAIL"] = (
        app.config.get("FROM_EMAIL")
        or os.environ.get("FROM_EMAIL")
        or app.config["SMTP_USER"]
    )

    # ------------------------
    # Init Mongo
    # ------------------------
    mongo.init_app(app)
    app.mongo = mongo  # attach mongo instance

    # ------------------------
    # ✅ Welcome / Landing Page
    # ------------------------
    @app.route("/", methods=["GET"])
    def landing():
        return render_template("welcome.html")

    @app.route("/welcome", methods=["GET"])
    def welcome():
        return render_template("welcome.html")

    # ------------------------
    # Register Blueprints
    # ------------------------
    from app.controllers.job_controller import job_bp
    from app.controllers.resume_controller import resume_bp
    from app.controllers.interview_controller import interview_bp

    app.register_blueprint(job_bp)  # /dashboard, /jobs, etc.
    app.register_blueprint(resume_bp, url_prefix="/screening")
    app.register_blueprint(interview_bp, url_prefix="/interview")

    # ------------------------
    # Health Check
    # ------------------------
    @app.route("/health", methods=["GET"])
    def health():
        return {
            "status": "ok",
            "db": mongo.db.name,
            "smtp_configured": bool(
                app.config.get("SMTP_USER") and app.config.get("SMTP_PASS")
            ),
        }

    return app