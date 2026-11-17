from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="admin", index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="SET NULL"), unique=True, nullable=True)
    full_name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(160), nullable=True)
    department = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship("Student", back_populates="account", foreign_keys=[student_id])
    announcements = db.relationship("Announcement", back_populates="author")
    audit_logs = db.relationship("AuditLog", back_populates="user")
    password_reset_tokens = db.relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self):
        return f"<User {self.username}>"