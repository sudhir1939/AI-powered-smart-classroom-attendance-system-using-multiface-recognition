import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "attendance.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    FACE_RECOGNITION_THRESHOLD = float(os.environ.get("FACE_RECOGNITION_THRESHOLD", "0.42"))
    FACE_FALLBACK_THRESHOLD = float(os.environ.get("FACE_FALLBACK_THRESHOLD", "0.86"))
    FACE_FALLBACK_MIN_SAMPLES = int(os.environ.get("FACE_FALLBACK_MIN_SAMPLES", "4"))
    FACE_RECOGNITION_MARGIN = float(os.environ.get("FACE_RECOGNITION_MARGIN", "0.12"))
    FACE_REGISTRATION_SAMPLES = int(os.environ.get("FACE_REGISTRATION_SAMPLES", "12"))
    EMBEDDING_ENCRYPTION_KEY = os.environ.get("EMBEDDING_ENCRYPTION_KEY", "")
    ATTENDANCE_ALERT_THRESHOLD = float(os.environ.get("ATTENDANCE_ALERT_THRESHOLD", "75"))
    BIOMETRIC_RETENTION_DAYS = int(os.environ.get("BIOMETRIC_RETENTION_DAYS", "365"))
    PASSWORD_RESET_MINUTES = int(os.environ.get("PASSWORD_RESET_MINUTES", "30"))
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")