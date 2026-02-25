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
    # File Upload Settings (temporary)
    # ==============================
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads")  # project/uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # ==============================
    # ML Model Paths
    # ==============================
    ML_MODEL_PATH = os.path.join(BASE_DIR, "ml_models", "resume_model.joblib")