from flask import Flask, redirect, url_for
from config import Config
from database.db import db
from models.user import User
from models.student import Student
from models.embedding import FaceEmbedding
from models.session import AttendanceSession
from models.attendance import Attendance
from models.announcement import Announcement
from models.audit import AuditLog, PasswordResetToken
from models.subject import Subject
from recognition.engine import engine
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.students import students_bp
from routes.attendance import attendance_bp
from routes.reports import reports_bp
from routes.admin import admin_bp
from routes.announcements import announcements_bp
from routes.mobile_api import mobile_api_bp


def create_app(test_db_uri=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_db_uri is not None:
        app.config["SQLALCHEMY_DATABASE_URI"] = test_db_uri

    db.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(announcements_bp)
    app.register_blueprint(mobile_api_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    with app.app_context():
        db.create_all()
        _migrate_legacy_users()

    if test_db_uri is None:
        engine.start_loading()

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))

    return app


def _migrate_legacy_users():
    """Add role/account columns to databases created before role-based login."""
    columns = {row[1] for row in db.session.execute(db.text("PRAGMA table_info(users)"))}
    if "role" not in columns:
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin'"))
    if "student_id" not in columns:
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN student_id INTEGER"))
    for column, definition in {
        "full_name": "VARCHAR(120)",
        "email": "VARCHAR(160)",
        "department": "VARCHAR(120)",
        "phone": "VARCHAR(30)",
    }.items():
        if column not in columns:
            db.session.execute(db.text(f"ALTER TABLE users ADD COLUMN {column} {definition}"))
    _add_column_if_missing("attendance", "corrected_at", "DATETIME")
    _add_column_if_missing("attendance", "corrected_by", "INTEGER")
    _add_column_if_missing("attendance", "correction_reason", "VARCHAR(500)")
    _add_column_if_missing("face_embeddings", "encrypted", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing("attendance_sessions", "classroom", "VARCHAR(80)")
    _add_column_if_missing("attendance_sessions", "created_by", "INTEGER")
    _add_column_if_missing("students", "consent_at", "DATETIME")
    _add_column_if_missing("students", "consent_version", "VARCHAR(20)")
    db.session.commit()


def _add_column_if_missing(table, column, definition):
    columns = {row[1] for row in db.session.execute(db.text(f"PRAGMA table_info({table})"))}
    if column not in columns:
        db.session.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)