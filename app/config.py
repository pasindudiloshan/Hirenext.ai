import os


class Config:
    # ==============================
    # Flask Core Settings
    # ==============================
    SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-hirenext-key")
    SESSION_PERMANENT = False  # job selection stays until browser closed / reset

    # ==============================
    # MongoDB Configuration (Local)
    # ==============================
    MONGO_URI = os.environ.get(
        "MONGO_URI",
        "mongodb://localhost:27017/hirenext_db"
    )

    # ==============================
    # Base Directories
    # ==============================
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # app/ folder

    # ==============================
    # File Upload Settings
    # ==============================
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads")  # project/uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # ==============================
    # ML Model Paths
    # ==============================
    ML_MODEL_PATH = os.path.join(
        BASE_DIR,
        "ml_models",
        "resume_model.joblib"
    )

    # ==============================
    # ✅ Gmail SMTP Configuration
    # ==============================
    # IMPORTANT:
    # - SMTP_PASS must be a Gmail App Password (NOT your normal Gmail password)
    # - Enable 2-Step Verification before generating App Password
    # ==============================

    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))

    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")

    # Default sender email (fallback to SMTP_USER)
    FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER)

    # Optional: Enable/Disable email sending
    EMAIL_ENABLED = bool(SMTP_USER and SMTP_PASS)