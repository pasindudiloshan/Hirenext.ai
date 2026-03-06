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
    # Secret Key
    # ------------------------
    app.secret_key = (
        app.config.get("SECRET_KEY")
        or os.environ.get("SECRET_KEY")
        or "super-secret-hirenext-key"
    )

    # ------------------------
    # AI Model Config
    # ------------------------
    app.config["SBERT_MODEL_PATH"] = (
        os.environ.get("SBERT_MODEL_PATH")
        or app.config.get("SBERT_MODEL_PATH")
    )

    app.config["WHISPER_MODEL_SIZE"] = (
        os.environ.get("WHISPER_MODEL_SIZE")
        or app.config.get("WHISPER_MODEL_SIZE")
        or "small"
    )

    os.environ.setdefault(
        "STT_WHISPER_MODEL",
        str(app.config["WHISPER_MODEL_SIZE"])
    )

    if app.config.get("SBERT_MODEL_PATH"):
        os.environ.setdefault(
            "SBERT_MODEL_PATH",
            str(app.config["SBERT_MODEL_PATH"])
        )

    app.config["AI_SCORING_MODE"] = (
        os.environ.get("AI_SCORING_MODE")
        or app.config.get("AI_SCORING_MODE")
        or "HYBRID"
    )

    # ------------------------
    # Emotion Recognition Config
    # ------------------------
    app.config["EMOTION_MODEL_PATH"] = (
        os.environ.get("EMOTION_MODEL_PATH")
        or app.config.get("EMOTION_MODEL_PATH")
        or "app/ml_models/emotion_model.keras"
    )

    app.config["EMOTION_LABELS_PATH"] = (
        os.environ.get("EMOTION_LABELS_PATH")
        or app.config.get("EMOTION_LABELS_PATH")
        or "app/ml_models/emotion_labels.json"
    )

    # ✅ Your trained model expects 128x128
    app.config["EMOTION_INPUT_SIZE"] = (
        os.environ.get("EMOTION_INPUT_SIZE")
        or app.config.get("EMOTION_INPUT_SIZE")
        or "128,128"
    )

    os.environ.setdefault(
        "EMOTION_MODEL_PATH",
        str(app.config["EMOTION_MODEL_PATH"])
    )
    os.environ.setdefault(
        "EMOTION_LABELS_PATH",
        str(app.config["EMOTION_LABELS_PATH"])
    )
    os.environ.setdefault(
        "EMOTION_INPUT_SIZE",
        str(app.config["EMOTION_INPUT_SIZE"])
    )

    # ------------------------
    # SMTP Config
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
    # Ensure Required Indexes
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
    from app.controllers.auth_controller import auth_bp
    from app.controllers.job_controller import job_bp
    from app.controllers.resume_controller import resume_bp
    from app.controllers.interview_controller import interview_bp
    from app.controllers.interview_ai_controller import interview_ai_bp
    from app.controllers.emotion_controller import emotion_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(resume_bp, url_prefix="/screening")
    app.register_blueprint(interview_bp, url_prefix="/interview")
    app.register_blueprint(interview_ai_bp)
    app.register_blueprint(emotion_bp)

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
        }

    return app