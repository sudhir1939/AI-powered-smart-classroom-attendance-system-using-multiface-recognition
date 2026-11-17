from datetime import datetime

from database.db import db


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (db.UniqueConstraint("student_id", "session_id", name="uq_attendance_student_session"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    similarity = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Present")
    corrected_at = db.Column(db.DateTime, nullable=True)
    corrected_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    correction_reason = db.Column(db.String(500), nullable=True)
    student = db.relationship("Student", back_populates="attendance")
    session = db.relationship("AttendanceSession", back_populates="attendance")
    corrected_by_user = db.relationship("User", foreign_keys=[corrected_by])
