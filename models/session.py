from datetime import datetime

from database.db import db


class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(120), nullable=False)
    division = db.Column(db.String(30), nullable=False, index=True)
    classroom = db.Column(db.String(80), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    attendance = db.relationship("Attendance", back_populates="session", cascade="all, delete-orphan")
    creator = db.relationship("User", foreign_keys=[created_by])
