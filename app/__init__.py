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
    # AI Model Config (SBERT path optional)
    # ------------------------
    # If you want to use local SBERT model folder:
    # export SBERT_MODEL_PATH=app/data/ml_models/embedder_all_MiniLM_L6_v2
    app.config["SBERT_MODEL_PATH"] = (
        os.environ.get("SBERT_MODEL_PATH")
        or app.config.get("SBERT_MODEL_PATH")
    )

    # Whisper model size (small | base | medium)
    app.config["WHISPER_MODEL_SIZE"] = (
        os.environ.get("WHISPER_MODEL_SIZE")
        or "small"
    )

    # ✅ IMPORTANT: Map your config to the env var used by STTService
    # STTService reads STT_WHISPER_MODEL, so keep them aligned.
    os.environ.setdefault("STT_WHISPER_MODEL", str(app.config["WHISPER_MODEL_SIZE"]))

    # ✅ Optional: ensure SBERT env var exists for EvaluatorService (it reads env)
    if app.config.get("SBERT_MODEL_PATH"):
        os.environ.setdefault("SBERT_MODEL_PATH", str(app.config["SBERT_MODEL_PATH"]))

    # Hybrid scoring toggle
    app.config["AI_SCORING_MODE"] = (
        os.environ.get("AI_SCORING_MODE")
        or "HYBRID"   # A_ONLY | HYBRID
    )

    # ------------------------
    # SMTP Config (Gmail SMTP)
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

    app.config["FROM_EMAIL"] = (
        app.config.get("FROM_EMAIL")
        or os.environ.get("FROM_EMAIL")
        or app.config["SMTP_USER"]
    )

    # ------------------------
    # Init Mongo
    # ------------------------
    mongo.init_app(app)
    app.mongo = mongo

    # ------------------------
    # Ensure Required Indexes (Performance)
    # ------------------------
    with app.app_context():
        db = mongo.db
        db.interview_attempts.create_index("session_id", unique=True)
        db.interview_attempts.create_index("interview_id")

    # ------------------------
    # Welcome / Landing Page
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
    from app.controllers.interview_ai_controller import interview_ai_bp

    app.register_blueprint(job_bp)
    app.register_blueprint(resume_bp, url_prefix="/screening")
    app.register_blueprint(interview_bp, url_prefix="/interview")
    app.register_blueprint(interview_ai_bp)  # /interview-ai

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
            "ai_mode": app.config.get("AI_SCORING_MODE"),
            "whisper_model": app.config.get("WHISPER_MODEL_SIZE"),
        }

    return app