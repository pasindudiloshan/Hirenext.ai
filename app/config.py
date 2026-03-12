import os


class Config:
    # =================================
    # Flask Core Settings
    # =================================
    SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-hirenext-key")
    SESSION_PERMANENT = False

    # =================================
    # MongoDB Configuration
    # =================================
    MONGO_URI = os.environ.get(
        "MONGO_URI",
        "mongodb://localhost:27017/hirenext_db"
    )

    # =================================
    # Base Directories
    # =================================
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # =================================
    # File Upload Settings
    # =================================
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # ensure uploads folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # =================================
    # ML Model Paths
    # =================================
    ML_MODEL_PATH = os.environ.get(
        "ML_MODEL_PATH",
        os.path.join(BASE_DIR, "ml_models", "resume_model.joblib")
    )

    # =================================
    # AI Models
    # =================================
    SBERT_MODEL_PATH = os.environ.get(
        "SBERT_MODEL_PATH",
        os.path.join(BASE_DIR, "ml_models", "embedder_all_MiniLM_L6_v2")
    )

    WHISPER_MODEL_SIZE = os.environ.get(
        "WHISPER_MODEL_SIZE",
        "small"
    )

    AI_SCORING_MODE = os.environ.get(
        "AI_SCORING_MODE",
        "HYBRID"
    )

    # =================================
    # Emotion Recognition
    # =================================
    EMOTION_MODEL_PATH = os.environ.get(
        "EMOTION_MODEL_PATH",
        os.path.join(BASE_DIR, "ml_models", "emotion_model.keras")
    )

    EMOTION_LABELS_PATH = os.environ.get(
        "EMOTION_LABELS_PATH",
        os.path.join(BASE_DIR, "ml_models", "emotion_labels.json")
    )

    # convert "128,128" → (128,128)
    _emotion_size = os.environ.get("EMOTION_INPUT_SIZE", "128,128").split(",")
    EMOTION_INPUT_SIZE = (int(_emotion_size[0]), int(_emotion_size[1]))

    # =================================
    # Gmail SMTP Configuration
    # =================================
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))

    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")

    FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER)

    EMAIL_ENABLED = bool(SMTP_USER and SMTP_PASS)

# =================================
# Admin Authentication
# =================================
ADMIN_EMAIL = "admin@hirenext.ai"
ADMIN_PASSWORD = "Admin@123"