import os

from flask import Flask, render_template
from flask_pymongo import PyMongo

mongo = PyMongo()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ------------------------
    # Load Config
    # ------------------------
    app.config.from_object("app.config.Config")

    # ------------------------
    # Force Admin Credentials
    # ------------------------
    app.config["ADMIN_EMAIL"] = "admin@hirenext.ai"
    app.config["ADMIN_PASSWORD"] = "Admin@123"

    # ------------------------
    # Secret Key
    # ------------------------
    app.secret_key = app.config["SECRET_KEY"]

    # ------------------------
    # Sync important config to environment
    # ------------------------
    if app.config.get("WHISPER_MODEL_SIZE"):
        os.environ.setdefault(
            "STT_WHISPER_MODEL",
            str(app.config["WHISPER_MODEL_SIZE"])
        )

    if app.config.get("SBERT_MODEL_PATH"):
        os.environ.setdefault(
            "SBERT_MODEL_PATH",
            str(app.config["SBERT_MODEL_PATH"])
        )

    if app.config.get("EMOTION_MODEL_PATH"):
        os.environ.setdefault(
            "EMOTION_MODEL_PATH",
            str(app.config["EMOTION_MODEL_PATH"])
        )

    if app.config.get("EMOTION_LABELS_PATH"):
        os.environ.setdefault(
            "EMOTION_LABELS_PATH",
            str(app.config["EMOTION_LABELS_PATH"])
        )

    if app.config.get("EMOTION_INPUT_SIZE"):
        emotion_input_size = app.config["EMOTION_INPUT_SIZE"]
        if isinstance(emotion_input_size, tuple):
            emotion_input_size = ",".join(map(str, emotion_input_size))
        os.environ.setdefault("EMOTION_INPUT_SIZE", str(emotion_input_size))

    # ------------------------
    # Init Mongo
    # ------------------------
    mongo.init_app(app)
    app.mongo = mongo

    # ------------------------
    # Ensure Required Indexes
    # ------------------------
    with app.app_context():
        db = mongo.db

        # Interview related indexes
        db.interview_attempts.create_index("session_id", unique=True)
        db.interview_attempts.create_index("interview_id")

        # Staff indexes
        db.staff.create_index("email", unique=True)
        db.staff.create_index("staff_code", unique=True)
        db.staff.create_index("created_at")
        db.staff.create_index("status")

        # Candidate indexes
        db.candidates.create_index("email", unique=True)
        db.candidates.create_index("created_at")
        db.candidates.create_index("status")

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
    from app.controllers.auth_controller import auth_bp
    from app.controllers.job_controller import job_bp
    from app.controllers.resume_controller import resume_bp
    from app.controllers.interview_controller import interview_bp
    from app.controllers.interview_ai_controller import interview_ai_bp
    from app.controllers.emotion_controller import emotion_bp
    from app.controllers.admin_controller import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(resume_bp, url_prefix="/screening")
    app.register_blueprint(interview_bp, url_prefix="/interview")
    app.register_blueprint(interview_ai_bp)
    app.register_blueprint(emotion_bp)
    app.register_blueprint(admin_bp)

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
            "emotion_model_path": app.config.get("EMOTION_MODEL_PATH"),
            "emotion_labels_path": app.config.get("EMOTION_LABELS_PATH"),
            "emotion_input_size": app.config.get("EMOTION_INPUT_SIZE"),
            "admin_email_configured": bool(app.config.get("ADMIN_EMAIL")),
            "admin_password_set": bool(app.config.get("ADMIN_PASSWORD")),
            "staff_collection_ready": True,
            "staff_model_enabled": True,
            "candidate_collection_ready": True,
            "candidate_model_enabled": True,
            "auth_service_enabled": True,
        }

    return app